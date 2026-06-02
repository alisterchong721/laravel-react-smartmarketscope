<?php

namespace App\Http\Service;

use App\Models\NewsArticle;
use App\Support\TrackedMarketAsset;
use Carbon\Carbon;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use RuntimeException;

class NewsIngestionService
{
    public function previewLatestArticles(array $filters = []): array
    {
        $lookbackHours = isset($filters['lookback_hours']) ? max(1, (int) $filters['lookback_hours']) : (int) config('services.news_sentiment.lookback_hours', 24);
        $publishedAfter = now()->subHours($lookbackHours);
        $items = $this->requestSourceArticles($publishedAfter, isset($filters['limit']) ? (int) $filters['limit'] : null);

        return [
            'provider' => 'marketaux',
            'fetched_at' => now()->toIso8601String(),
            'published_after' => $publishedAfter->toIso8601String(),
            'total_items' => count($items),
            'items' => array_map(function (array $item): array {
                return [
                    'provider_article_id' => $item['uuid'] ?? null,
                    'source_name' => $item['source'] ?? null,
                    'title' => $item['title'] ?? null,
                    'summary' => $item['description'] ?? null,
                    'snippet' => $item['snippet'] ?? null,
                    'url' => $item['url'] ?? null,
                    'image_url' => $item['image_url'] ?? null,
                    'language' => $item['language'] ?? null,
                    'published_at' => $item['published_at'] ?? null,
                    'entities' => $item['entities'] ?? [],
                    'detected_assets' => TrackedMarketAsset::inferRelevantAssets($item),
                    'raw_payload' => $item,
                ];
            }, $items),
        ];
    }

    public function syncLatestArticles(bool $forceRefresh = false): array
    {
        $lookbackHours = (int) config('services.news_sentiment.lookback_hours', 24);
        $publishedAfter = $forceRefresh
            ? now()->subHours($lookbackHours)
            : $this->resolvePublishedAfter($lookbackHours);
        $items = $this->requestSourceArticles($publishedAfter);

        $inserted = 0;
        $updated = 0;
        $skipped = 0;
        $articleIdsForAnalysis = [];

        foreach ($items as $item) {
            $relevantAssets = TrackedMarketAsset::inferRelevantAssets($item);

            if (empty($relevantAssets)) {
                $skipped++;
                continue;
            }

            $url = (string) ($item['url'] ?? '');
            $urlHash = hash('sha256', $url);

            if ($url === '') {
                $skipped++;
                continue;
            }

            $providerArticleId = $item['uuid'] ?? null;
            $article = $providerArticleId
                ? NewsArticle::query()->firstOrNew([
                    'provider' => 'marketaux',
                    'provider_article_id' => $providerArticleId,
                ])
                : NewsArticle::query()->firstOrNew([
                    'url_hash' => $urlHash,
                ]);

            $isNew = !$article->exists;
            $article->fill([
                'provider' => 'marketaux',
                'provider_article_id' => $providerArticleId,
                'source_name' => $item['source'] ?? null,
                'title' => $item['title'] ?? 'Untitled Article',
                'summary' => $item['description'] ?? null,
                'snippet' => $item['snippet'] ?? null,
                'url' => $url,
                'url_hash' => $urlHash,
                'image_url' => $item['image_url'] ?? null,
                'language' => $item['language'] ?? null,
                'published_at' => $item['published_at'] ?? null,
                'fetched_at' => now(),
                'raw_payload' => $item,
            ]);

            if ($isNew || $article->analysis_status !== NewsArticle::STATUS_COMPLETED) {
                $article->analysis_status = NewsArticle::STATUS_PENDING;
                $article->analysis_error = null;
            }

            $article->save();
            $articleIdsForAnalysis[] = $article->id;

            if ($isNew) {
                $inserted++;
            } else {
                $updated++;
            }
        }

        return [
            'provider' => 'marketaux',
            'fetched_at' => now()->toIso8601String(),
            'published_after' => $publishedAfter->toIso8601String(),
            'inserted' => $inserted,
            'updated' => $updated,
            'skipped' => $skipped,
            'analysis_candidates' => array_values(array_unique($articleIdsForAnalysis)),
        ];
    }

    private function requestSourceArticles(Carbon $publishedAfter, ?int $limit = null): array
    {
        $apiKey = config('services.marketaux.api_key');

        if (!$apiKey) {
            throw new RuntimeException('MARKETAUX_API_KEY is not configured.');
        }

        $resolvedLimit = $limit !== null
            ? max(1, min($limit, 100))
            : (int) config('services.marketaux.limit', 25);

        $response = Http::acceptJson()
            ->timeout((int) config('services.marketaux.timeout', 20))
            ->get(config('services.marketaux.endpoint'), [
                'api_token' => $apiKey,
                'language' => config('services.marketaux.language', 'en'),
                'must_have_entities' => 'true',
                'sort' => 'published_desc',
                'limit' => $resolvedLimit,
                'published_after' => $publishedAfter->utc()->format('Y-m-d\TH:i'),
            ]);

        if ($response->failed()) {
            throw new RuntimeException('Unable to fetch market news from MarketAux.');
        }

        $payload = $response->json();
        $items = $payload['data'] ?? null;

        if (!is_array($items)) {
            throw new RuntimeException('MarketAux returned an unexpected response format.');
        }

        return $items;
    }

    private function resolvePublishedAfter(int $lookbackHours): Carbon
    {
        $latestPublishedAt = NewsArticle::query()->max('published_at');

        if (!$latestPublishedAt) {
            return now()->subHours($lookbackHours);
        }

        return Carbon::parse($latestPublishedAt)->subHours(2);
    }
}
