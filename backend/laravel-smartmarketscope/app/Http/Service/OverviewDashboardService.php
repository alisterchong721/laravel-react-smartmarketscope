<?php

namespace App\Http\Service;

use App\Models\CotReport;
use App\Models\NewsArticle;
use App\Models\NewsArticleAssetImpact;
use App\Models\RetailSentiment;
use Illuminate\Database\Eloquent\Builder;
use Throwable;

class OverviewDashboardService
{
    private const DEFAULT_NEWS_LOOKBACK_HOURS = 24;
    private const FUNDAMENTAL_MAX_EXPECTED_SCORE = 10;

    private const SENTIMENT_WEIGHTS = [
        'cot' => 0.35,
        'retail' => 0.25,
        'news' => 0.40,
    ];

    private const OVERALL_WEIGHTS = [
        'fundamental' => 0.40,
        'sentiment' => 0.45,
        'seasonality' => 0.15,
    ];

    public function __construct(
        private FundamentalDataService $fundamentalDataService,
        private CotReportService $cotReportService,
        private RetailSentimentService $retailSentimentService,
        private NewsSentimentService $newsSentimentService,
        private SeasonalityAnalysisService $seasonalityAnalysisService,
    ) {
    }

    public function getOverview(array $filters = []): array
    {
        $assets = $this->resolveRequestedAssets($filters['assets'] ?? ($filters['asset'] ?? null));
        $refresh = (bool) ($filters['refresh'] ?? false);
        $newsLookbackHours = $this->resolveNewsLookbackHours($filters['news_lookback_hours'] ?? null);

        $cotIndex = $this->buildCotIndex($assets, $refresh);
        $retailIndex = $this->buildRetailIndex($assets, $refresh);
        $newsIndex = $this->buildNewsIndex($assets, $newsLookbackHours, $refresh);
        $seasonalityIndex = $this->buildSeasonalityIndex($assets, $refresh);

        $items = [];

        foreach ($assets as $asset) {
            $fundamental = $this->buildFundamentalComponent($asset);
            $cot = $cotIndex['items'][$asset] ?? $this->unavailableComponent('cot', $cotIndex['error'] ?? 'COT data is not available for this asset.');
            $retail = $retailIndex['items'][$asset] ?? $this->unavailableComponent('retail', $retailIndex['error'] ?? 'Retail sentiment is not available for this asset.');
            $news = $newsIndex['items'][$asset] ?? $this->unavailableComponent('news', $newsIndex['error'] ?? 'News sentiment is not available for this asset.');
            $seasonality = $seasonalityIndex['items'][$asset] ?? $this->unavailableComponent('seasonality', $seasonalityIndex['error'] ?? 'Seasonality data is not available for this asset.');

            $sentiment = $this->weightedComponentScore([
                'cot' => $cot,
                'retail' => $retail,
                'news' => $news,
            ], self::SENTIMENT_WEIGHTS);

            $overall = $this->weightedComponentScore([
                'fundamental' => $fundamental,
                'sentiment' => $sentiment,
                'seasonality' => $seasonality,
            ], self::OVERALL_WEIGHTS);

            $items[] = [
                'asset_symbol' => $asset,
                'display_name' => $this->displayName($asset),
                'base_currency' => CotReport::ASSET_MARKET_MAP[$asset]['base_currency'],
                'quote_currency' => CotReport::ASSET_MARKET_MAP[$asset]['quote_currency'],
                'fundamental' => $fundamental,
                'sentiment' => [
                    ...$sentiment,
                    'components' => [
                        'cot' => $cot,
                        'retail' => $retail,
                        'news' => $news,
                    ],
                ],
                'seasonality' => $seasonality,
                'overall' => $overall,
            ];
        }

        return [
            'summary' => [
                'total_assets' => count($items),
                'bias_scale' => $this->biasScale(),
                'weights' => [
                    'sentiment' => self::SENTIMENT_WEIGHTS,
                    'overall' => self::OVERALL_WEIGHTS,
                ],
                'latest_cot_report_date' => $cotIndex['report_date'] ?? null,
                'latest_news_published_at' => $newsIndex['latest_published_at'] ?? null,
                'seasonality_month' => $seasonalityIndex['month_name'] ?? now()->format('F'),
                'news_lookback_hours' => $newsLookbackHours,
                'generated_at' => now()->toIso8601String(),
            ],
            'items' => $items,
            'available_filters' => $this->getFiltersMeta(),
            'source_status' => [
                'cot' => [
                    'available' => empty($cotIndex['error']),
                    'error' => $cotIndex['error'] ?? null,
                ],
                'retail' => [
                    'available' => empty($retailIndex['error']),
                    'error' => $retailIndex['error'] ?? null,
                ],
                'news' => [
                    'available' => empty($newsIndex['error']),
                    'error' => $newsIndex['error'] ?? null,
                ],
                'seasonality' => [
                    'available' => empty($seasonalityIndex['error']),
                    'error' => $seasonalityIndex['error'] ?? null,
                ],
            ],
        ];
    }

    public function getFiltersMeta(): array
    {
        return [
            'supported_assets' => array_map(
                fn(string $asset) => [
                    'symbol' => $asset,
                    'display_name' => $this->displayName($asset),
                    'base_currency' => CotReport::ASSET_MARKET_MAP[$asset]['base_currency'],
                    'quote_currency' => CotReport::ASSET_MARKET_MAP[$asset]['quote_currency'],
                ],
                $this->supportedAssets()
            ),
            'default_assets' => $this->supportedAssets(),
            'bias_scale' => $this->biasScale(),
            'default_news_lookback_hours' => self::DEFAULT_NEWS_LOOKBACK_HOURS,
        ];
    }

    private function buildFundamentalComponent(string $asset): array
    {
        $result = $this->fundamentalDataService->calculatePairImpact($asset);

        if (isset($result['error'])) {
            return $this->unavailableComponent('fundamental', $result['error']);
        }

        $score = $this->clampScore(
            (($result['pair_score'] ?? 0) / self::FUNDAMENTAL_MAX_EXPECTED_SCORE) * 100
        );

        return [
            'available' => true,
            'score' => $score,
            'bias' => $this->biasFromScore($score),
            'raw_pair_score' => (int) ($result['pair_score'] ?? 0),
            'base_score' => (int) ($result['base_score'] ?? 0),
            'quote_score' => (int) ($result['quote_score'] ?? 0),
            'base_country' => $result['base_country'] ?? null,
            'quote_country' => $result['quote_country'] ?? null,
            'max_expected_score' => self::FUNDAMENTAL_MAX_EXPECTED_SCORE,
        ];
    }

    private function buildCotIndex(array $assets, bool $refresh): array
    {
        try {
            $payload = $this->cotReportService->getCotReport([
                'assets' => $assets,
                'refresh' => $refresh,
            ]);
        } catch (Throwable $exception) {
            return ['items' => [], 'error' => $exception->getMessage()];
        }

        $items = [];

        foreach ($payload['items'] ?? [] as $item) {
            $category = $item['categories'][CotReport::CATEGORY_NON_COMMERCIAL] ?? null;

            if (!$category) {
                continue;
            }

            $score = $this->clampDecimalScore(
                ((float) ($category['long_percentage'] ?? 0)) - ((float) ($category['short_percentage'] ?? 0))
            );
            $netPosition = (int) ($category['net_position'] ?? 0);

            $items[$item['asset_symbol']] = [
                'available' => true,
                'score' => $score,
                'bias' => $this->biasFromNetPosition($netPosition),
                'report_date' => $item['report_date'] ?? null,
                'long_percentage' => round((float) ($category['long_percentage'] ?? 0), 2),
                'short_percentage' => round((float) ($category['short_percentage'] ?? 0), 2),
                'net_position' => $netPosition,
                'sentiment_bias' => $category['sentiment_bias'] ?? null,
            ];
        }

        return [
            'items' => $items,
            'report_date' => $payload['report_date'] ?? null,
        ];
    }

    private function buildRetailIndex(array $assets, bool $refresh): array
    {
        $items = [];
        $error = null;

        foreach ($assets as $asset) {
            try {
                $payload = $this->retailSentimentService->getRetailSentiment([
                    'group_by' => RetailSentiment::GROUP_BY_PAIRS,
                    'pair' => $asset,
                    'refresh' => $refresh,
                ]);
            } catch (Throwable $exception) {
                $error = $exception->getMessage();
                continue;
            }

            $averageBuy = (float) ($payload['summary']['average_buy_percentage'] ?? 50);
            $score = $this->clampScore((50 - $averageBuy) * 2);

            $items[$asset] = [
                'available' => true,
                'score' => $score,
                'bias' => $this->biasFromScore($score),
                'average_buy_percentage' => round($averageBuy, 2),
                'average_sell_percentage' => round((float) ($payload['summary']['average_sell_percentage'] ?? (100 - $averageBuy)), 2),
                'total_brokers' => (int) ($payload['summary']['total_rows'] ?? 0),
                'signal' => $score > 0 ? 'buy_bias' : ($score < 0 ? 'sell_bias' : 'neutral_bias'),
                'source' => $payload['source'] ?? null,
            ];
        }

        return [
            'items' => $items,
            'error' => empty($items) ? $error : null,
        ];
    }

    private function buildNewsIndex(array $assets, int $lookbackHours, bool $refresh): array
    {
        $sync = null;

        if ($refresh) {
            try {
                $sync = $this->newsSentimentService->syncLatestData(true);
            } catch (Throwable $exception) {
                return ['items' => [], 'error' => $exception->getMessage()];
            }
        }

        $fromDate = now()->subHours($lookbackHours);
        $rows = NewsArticleAssetImpact::query()
            ->with('article')
            ->whereIn('asset_symbol', $assets)
            ->where('published_at', '>=', $fromDate)
            ->whereHas('article', function (Builder $builder): void {
                $builder->where('analysis_status', NewsArticle::STATUS_COMPLETED);
            })
            ->orderByDesc('published_at')
            ->get();

        $items = [];

        foreach ($assets as $asset) {
            $assetRows = $rows->where('asset_symbol', $asset);

            if ($assetRows->isEmpty()) {
                $items[$asset] = [
                    'available' => true,
                    'score' => 0,
                    'bias' => 'neutral',
                    'total_articles' => 0,
                    'bullish_count' => 0,
                    'bearish_count' => 0,
                    'neutral_count' => 0,
                    'average_impact_score' => 0,
                    'average_confidence_score' => 0,
                    'latest_published_at' => null,
                ];

                continue;
            }

            $articleScores = $assetRows->map(function (NewsArticleAssetImpact $impact): float {
                $directionMultiplier = match ($impact->direction) {
                    NewsArticleAssetImpact::DIRECTION_BULLISH => 1,
                    NewsArticleAssetImpact::DIRECTION_BEARISH => -1,
                    default => 0,
                };

                return $directionMultiplier * (int) $impact->impact_score * ((int) $impact->confidence_score / 100);
            });

            $score = $this->clampScore($articleScores->avg() ?? 0);

            $items[$asset] = [
                'available' => true,
                'score' => $score,
                'bias' => $this->biasFromScore($score),
                'total_articles' => $assetRows->count(),
                'bullish_count' => $assetRows->where('direction', NewsArticleAssetImpact::DIRECTION_BULLISH)->count(),
                'bearish_count' => $assetRows->where('direction', NewsArticleAssetImpact::DIRECTION_BEARISH)->count(),
                'neutral_count' => $assetRows->where('direction', NewsArticleAssetImpact::DIRECTION_NEUTRAL)->count(),
                'average_impact_score' => round($assetRows->avg('impact_score'), 2),
                'average_confidence_score' => round($assetRows->avg('confidence_score'), 2),
                'latest_published_at' => optional($assetRows->first()->published_at)->toIso8601String(),
            ];
        }

        return [
            'items' => $items,
            'latest_published_at' => optional($rows->first()?->published_at)->toIso8601String(),
            'sync' => $sync,
        ];
    }

    private function buildSeasonalityIndex(array $assets, bool $refresh): array
    {
        $month = (int) now()->format('n');
        $monthName = now()->format('F');

        try {
            $payload = $this->seasonalityAnalysisService->getSeasonality([
                'assets' => $assets,
                'period' => 'monthly',
                'years' => 10,
                'refresh' => $refresh,
            ]);
        } catch (Throwable $exception) {
            return [
                'items' => [],
                'month' => $month,
                'month_name' => $monthName,
                'error' => $exception->getMessage(),
            ];
        }

        $items = [];

        foreach ($payload['items'] ?? [] as $item) {
            $monthData = collect($item['monthly'] ?? [])->firstWhere('month', $month);

            if (!$monthData) {
                continue;
            }

            $averageReturn = (float) ($monthData['average_return'] ?? 0);
            $score = $this->clampScore($averageReturn * 20);

            $items[$item['asset_symbol']] = [
                'available' => true,
                'score' => $score,
                'bias' => $this->biasFromScore($score),
                'month' => $month,
                'month_name' => $monthData['month_name'] ?? $monthName,
                'average_return' => round($averageReturn, 2),
                'median_return' => round((float) ($monthData['median_return'] ?? 0), 2),
                'observations' => (int) ($monthData['observations'] ?? 0),
                'score_formula' => 'average_month_return * 20',
            ];
        }

        return [
            'items' => $items,
            'month' => $month,
            'month_name' => $monthName,
            'error' => empty($items) ? 'No seasonality rows matched the current month.' : null,
        ];
    }

    private function weightedComponentScore(array $components, array $weights): array
    {
        $weightedScore = 0;
        $availableWeight = 0;

        foreach ($components as $key => $component) {
            if (!($component['available'] ?? false)) {
                continue;
            }

            $weight = $weights[$key] ?? 0;
            $weightedScore += ((float) ($component['score'] ?? 0)) * $weight;
            $availableWeight += $weight;
        }

        $score = $availableWeight > 0
            ? $this->clampWeightedScore($weightedScore / $availableWeight)
            : 0;

        return [
            'available' => $availableWeight > 0,
            'score' => $score,
            'bias' => $this->biasFromScore($score),
            'available_weight' => round($availableWeight, 2),
        ];
    }

    private function unavailableComponent(string $source, string $message): array
    {
        return [
            'available' => false,
            'score' => null,
            'bias' => null,
            'error' => $message,
            'source' => $source,
        ];
    }

    private function resolveRequestedAssets(mixed $assets): array
    {
        if ($assets === null || $assets === '') {
            return $this->supportedAssets();
        }

        $assets = is_array($assets) ? $assets : explode(',', (string) $assets);
        $resolved = [];

        foreach ($assets as $asset) {
            $normalized = CotReport::normalizeAsset($asset);

            if ($normalized && in_array($normalized, $this->supportedAssets(), true)) {
                $resolved[] = $normalized;
            }
        }

        return array_values(array_unique($resolved)) ?: $this->supportedAssets();
    }

    private function supportedAssets(): array
    {
        return array_values(array_intersect(
            CotReport::supportedAssets(),
            RetailSentiment::supportedPairs()
        ));
    }

    private function resolveNewsLookbackHours(mixed $hours): int
    {
        $resolved = (int) ($hours ?: self::DEFAULT_NEWS_LOOKBACK_HOURS);

        return max(1, min(168, $resolved));
    }

    private function displayName(string $asset): string
    {
        return CotReport::ASSET_MARKET_MAP[$asset]['display_name'] ?? $asset;
    }

    private function clampScore(float $score): int
    {
        return (int) round(max(-100, min(100, $score)));
    }

    private function clampDecimalScore(float $score): float|int
    {
        $rounded = round(max(-100, min(100, $score)), 2);

        return fmod($rounded, 1.0) === 0.0
            ? (int) $rounded
            : $rounded;
    }

    private function clampWeightedScore(float $score): float|int|string
    {
        $rounded = round(max(-100, min(100, $score)), 1);

        return fmod($rounded, 1.0) === 0.0
            ? (int) $rounded
            : number_format($rounded, 1, '.', '');
    }

    private function biasFromScore(float|int $score): string
    {
        if ($score >= 60) {
            return 'strong_bullish';
        }

        if ($score > 0) {
            return 'bullish';
        }

        if ($score == 0) {
            return 'neutral';
        }

        if ($score > -60) {
            return 'bearish';
        }

        return 'strong_bearish';
    }

    private function biasFromNetPosition(int $netPosition): string
    {
        if ($netPosition >= 60000) {
            return 'strong_bullish';
        }

        if ($netPosition > 0) {
            return 'bullish';
        }

        if ($netPosition === 0) {
            return 'neutral';
        }

        if ($netPosition > -60000) {
            return 'bearish';
        }

        return 'strong_bearish';
    }

    private function biasScale(): array
    {
        return [
            'strong_bullish' => ['min' => 60, 'max' => 100],
            'bullish' => ['min' => 0.1, 'max' => 59.9],
            'neutral' => ['min' => 0, 'max' => 0],
            'bearish' => ['min' => -59.9, 'max' => -0.1],
            'strong_bearish' => ['min' => -100, 'max' => -60],
        ];
    }
}
