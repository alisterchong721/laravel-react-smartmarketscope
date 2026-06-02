<?php

namespace App\Http\Service;

use App\Models\NewsArticle;
use App\Models\NewsArticleAssetImpact;
use App\Support\TrackedMarketAsset;
use Illuminate\Support\Facades\Http;
use RuntimeException;

class OpenAiNewsAnalysisService
{
    public function analyzeArticle(NewsArticle $article): array
    {
        $apiKey = config('services.openai.api_key');

        if (!$apiKey) {
            throw new RuntimeException('OPENAI_API_KEY is not configured.');
        }

        $response = Http::withToken($apiKey)
            ->acceptJson()
            ->timeout((int) config('services.openai.timeout', 45))
            ->post(config('services.openai.endpoint'), [
                'model' => config('services.openai.model', 'gpt-5-nano'),
                'input' => [
                    [
                        'role' => 'system',
                        'content' => [
                            [
                                'type' => 'input_text',
                                'text' => $this->systemPrompt(),
                            ],
                        ],
                    ],
                    [
                        'role' => 'user',
                        'content' => [
                            [
                                'type' => 'input_text',
                                'text' => json_encode($this->buildUserPayload($article), JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES),
                            ],
                        ],
                    ],
                ],
            ]);

        if ($response->failed()) {
            throw new RuntimeException('OpenAI news analysis request failed.');
        }

        $payload = $response->json();
        $content = $this->extractOutputText($payload);

        if (!$content) {
            throw new RuntimeException('OpenAI did not return any analysis content.');
        }

        $decoded = json_decode($this->sanitizeJson($content), true);

        if (!is_array($decoded)) {
            throw new RuntimeException('OpenAI returned invalid JSON for the news analysis.');
        }

        return $this->normalizeAnalysisPayload($decoded, $article);
    }

    private function systemPrompt(): string
    {
        return <<<'PROMPT'
You are a market news impact classifier for a trading dashboard.

Analyze the article and return JSON only.
Do not include markdown, code fences, or explanations outside JSON.

Rules:
1. Only use supported assets provided in the input.
2. Return at most 4 affected assets.
3. Direction must be one of: bullish, bearish, neutral.
4. impact_score and confidence_score must be integers from 0 to 100.
5. reasoning must be concise and specific to the asset.
6. If an article is not materially relevant to the supported assets, return an empty affected_assets array and set summary_sentiment to neutral.

Return this JSON object shape exactly:
{
  "summary_sentiment": "bullish|bearish|neutral",
  "market_theme": "short phrase",
  "global_impact_score": 0,
  "tags": ["tag1", "tag2"],
  "affected_assets": [
    {
      "asset_symbol": "EURUSD",
      "direction": "bullish|bearish|neutral",
      "sentiment_label": "short label",
      "impact_score": 0,
      "confidence_score": 0,
      "reasoning": "short reason"
    }
  ]
}
PROMPT;
    }

    private function buildUserPayload(NewsArticle $article): array
    {
        return [
            'article' => [
                'title' => $article->title,
                'summary' => $article->summary,
                'snippet' => $article->snippet,
                'source_name' => $article->source_name,
                'published_at' => optional($article->published_at)->toIso8601String(),
            ],
            'supported_assets' => TrackedMarketAsset::promptReference(),
        ];
    }

    private function extractOutputText(array $payload): ?string
    {
        if (!empty($payload['output_text']) && is_string($payload['output_text'])) {
            return $payload['output_text'];
        }

        foreach ($payload['output'] ?? [] as $outputItem) {
            foreach ($outputItem['content'] ?? [] as $contentItem) {
                if (($contentItem['type'] ?? null) === 'output_text' && !empty($contentItem['text'])) {
                    return $contentItem['text'];
                }
            }
        }

        return null;
    }

    private function sanitizeJson(string $content): string
    {
        $trimmed = trim($content);

        if (str_starts_with($trimmed, '```')) {
            $trimmed = preg_replace('/^```json\s*/', '', $trimmed) ?? $trimmed;
            $trimmed = preg_replace('/^```\s*/', '', $trimmed) ?? $trimmed;
            $trimmed = preg_replace('/\s*```$/', '', $trimmed) ?? $trimmed;
        }

        return trim($trimmed);
    }

    private function normalizeAnalysisPayload(array $payload, NewsArticle $article): array
    {
        $supportedAssets = TrackedMarketAsset::supportedSymbols();
        $impacts = [];

        foreach ($payload['affected_assets'] ?? [] as $impact) {
            $assetSymbol = TrackedMarketAsset::normalizeAsset($impact['asset_symbol'] ?? null);

            if (!$assetSymbol || !in_array($assetSymbol, $supportedAssets, true)) {
                continue;
            }

            $direction = $impact['direction'] ?? NewsArticleAssetImpact::DIRECTION_NEUTRAL;

            if (!in_array($direction, NewsArticleAssetImpact::supportedDirections(), true)) {
                $direction = NewsArticleAssetImpact::DIRECTION_NEUTRAL;
            }

            $impacts[] = [
                'asset_symbol' => $assetSymbol,
                'display_name' => TrackedMarketAsset::displayName($assetSymbol),
                'direction' => $direction,
                'sentiment_label' => $impact['sentiment_label'] ?? null,
                'impact_score' => $this->normalizeScore($impact['impact_score'] ?? 0),
                'confidence_score' => $this->normalizeScore($impact['confidence_score'] ?? 0),
                'reasoning' => $impact['reasoning'] ?? null,
                'market_theme' => $payload['market_theme'] ?? null,
                'tags' => array_values(array_filter(array_map(
                    fn($tag) => is_scalar($tag) ? trim((string) $tag) : null,
                    $payload['tags'] ?? []
                ))),
                'model_name' => config('services.openai.model', 'gpt-5-nano'),
                'published_at' => optional($article->published_at)->toDateTimeString(),
                'analyzed_at' => now()->toDateTimeString(),
                'analysis_payload' => $impact,
            ];
        }

        return [
            'summary_sentiment' => in_array(($payload['summary_sentiment'] ?? null), NewsArticleAssetImpact::supportedDirections(), true)
                ? $payload['summary_sentiment']
                : NewsArticleAssetImpact::DIRECTION_NEUTRAL,
            'market_theme' => $payload['market_theme'] ?? null,
            'global_impact_score' => $this->normalizeScore($payload['global_impact_score'] ?? 0),
            'tags' => array_values(array_filter(array_map(
                fn($tag) => is_scalar($tag) ? trim((string) $tag) : null,
                $payload['tags'] ?? []
            ))),
            'affected_assets' => $impacts,
            'raw_analysis' => $payload,
        ];
    }

    private function normalizeScore(mixed $value): int
    {
        $score = (int) round((float) $value);

        return max(0, min(100, $score));
    }
}
