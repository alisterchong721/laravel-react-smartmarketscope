<?php

namespace App\Http\Service;

use App\Jobs\AnalyzeNewsArticleImpactJob;
use App\Models\NewsArticle;
use App\Models\NewsArticleAssetImpact;
use App\Support\TrackedMarketAsset;
use Carbon\Carbon;
use Illuminate\Database\Eloquent\Builder;
use RuntimeException;

class NewsSentimentService
{
    public function __construct(private NewsIngestionService $newsIngestionService)
    {
    }

    public function getSourceNewsPreview(array $filters = []): array
    {
        return $this->newsIngestionService->previewLatestArticles($filters);
    }

    public function getNewsSentiment(array $filters = []): array
    {
        $syncStatus = $this->syncLatestData((bool) ($filters['refresh'] ?? false));
        $selectedAssets = $this->resolveRequestedAssets($filters['assets'] ?? ($filters['asset'] ?? null));
        $status = $this->resolveStatus($filters['status'] ?? NewsArticle::STATUS_COMPLETED);
        $direction = $this->resolveDirection($filters['direction'] ?? null);
        $limit = $this->resolveLimit($filters['limit'] ?? 20);
        $minImpactScore = $this->resolveScore($filters['min_impact_score'] ?? null);
        $fromDate = $this->resolveDate($filters['from_date'] ?? null);
        $toDate = $this->resolveDate($filters['to_date'] ?? null, true);

        $query = NewsArticleAssetImpact::query()
            ->with('article')
            ->whereIn('asset_symbol', TrackedMarketAsset::supportedSymbols())
            ->whereHas('article', function (Builder $builder) use ($status, $fromDate, $toDate): void {
                $builder->where('analysis_status', $status)
                    ->when($fromDate, fn(Builder $inner) => $inner->where('published_at', '>=', $fromDate))
                    ->when($toDate, fn(Builder $inner) => $inner->where('published_at', '<=', $toDate));
            })
            ->when(
                !empty($selectedAssets),
                fn(Builder $builder) => $builder->whereIn('asset_symbol', $selectedAssets)
            )
            ->when(
                $direction,
                fn(Builder $builder) => $builder->where('direction', $direction)
            )
            ->when(
                $minImpactScore !== null,
                fn(Builder $builder) => $builder->where('impact_score', '>=', $minImpactScore)
            )
            ->orderByDesc('published_at')
            ->orderByDesc('impact_score')
            ->limit($limit);

        $rows = $query->get();

        return [
            'selected_assets' => $selectedAssets,
            'summary' => $this->buildSummary($rows),
            'items' => $rows->map(fn(NewsArticleAssetImpact $impact) => $this->formatImpact($impact))->values()->all(),
            'available_filters' => $this->getFiltersMeta(),
            'sync' => $syncStatus,
            'pending_articles_count' => NewsArticle::query()->where('analysis_status', NewsArticle::STATUS_PENDING)->count(),
            'failed_articles_count' => NewsArticle::query()->where('analysis_status', NewsArticle::STATUS_FAILED)->count(),
        ];
    }

    public function getFetchedNews(array $filters = []): array
    {
        $status = $this->resolveStatus($filters['status'] ?? NewsArticle::STATUS_COMPLETED);
        $limit = $this->resolveLimit($filters['limit'] ?? 50);
        $fromDate = $this->resolveDate($filters['from_date'] ?? null);
        $toDate = $this->resolveDate($filters['to_date'] ?? null, true);

        $articles = NewsArticle::query()
            ->when(
                $status,
                fn(Builder $builder) => $builder->where('analysis_status', $status)
            )
            ->when(
                $fromDate,
                fn(Builder $builder) => $builder->where('published_at', '>=', $fromDate)
            )
            ->when(
                $toDate,
                fn(Builder $builder) => $builder->where('published_at', '<=', $toDate)
            )
            ->orderByDesc('published_at')
            ->orderByDesc('fetched_at')
            ->limit($limit)
            ->get();

        return [
            'summary' => [
                'total_items' => $articles->count(),
                'latest_published_at' => optional($articles->first()?->published_at)->toIso8601String(),
                'latest_fetched_at' => optional($articles->first()?->fetched_at)->toIso8601String(),
            ],
            'items' => $articles->map(fn(NewsArticle $article) => [
                'id' => $article->id,
                'provider' => $article->provider,
                'provider_article_id' => $article->provider_article_id,
                'source_name' => $article->source_name,
                'title' => $article->title,
                'summary' => $article->summary,
                'snippet' => $article->snippet,
                'url' => $article->url,
                'image_url' => $article->image_url,
                'language' => $article->language,
                'published_at' => optional($article->published_at)->toIso8601String(),
                'fetched_at' => optional($article->fetched_at)->toIso8601String(),
                'analysis_status' => $article->analysis_status,
                'summary_sentiment' => $article->summary_sentiment,
                'market_theme' => $article->market_theme,
                'global_impact_score' => $article->global_impact_score,
                'analyzed_at' => optional($article->analyzed_at)->toIso8601String(),
                'analysis_error' => $article->analysis_error,
            ])->values()->all(),
            'available_filters' => [
                'supported_statuses' => NewsArticle::supportedStatuses(),
                'default_status' => NewsArticle::STATUS_COMPLETED,
                'default_limit' => 50,
            ],
        ];
    }

    public function getFiltersMeta(): array
    {
        return [
            'supported_assets' => TrackedMarketAsset::supportedAssets(),
            'supported_directions' => NewsArticleAssetImpact::supportedDirections(),
            'supported_statuses' => NewsArticle::supportedStatuses(),
            'default_status' => NewsArticle::STATUS_COMPLETED,
            'default_limit' => 20,
            'source' => [
                'provider' => 'MarketAux',
                'provider_endpoint' => config('services.marketaux.endpoint'),
                'ai_provider' => 'OpenAI',
                'ai_model' => config('services.openai.model', 'gpt-5-nano'),
            ],
        ];
    }

    public function syncLatestData(bool $forceRefresh = false): array
    {
        $latestFetchedAt = NewsArticle::query()->max('fetched_at');
        $cacheSeconds = (int) config('services.news_sentiment.cache_seconds', 900);

        if (
            !$forceRefresh
            && $latestFetchedAt
            && Carbon::parse($latestFetchedAt)->greaterThanOrEqualTo(now()->subSeconds($cacheSeconds))
        ) {
            $queued = $this->dispatchPendingAnalyses();

            return [
                'mode' => 'database_only',
                'synced' => false,
                'queued_analysis_jobs' => $queued,
                'latest_fetched_at' => Carbon::parse($latestFetchedAt)->toIso8601String(),
            ];
        }

        $sync = $this->newsIngestionService->syncLatestArticles($forceRefresh);
        $queued = $this->dispatchPendingAnalyses($sync['analysis_candidates'] ?? []);

        return [
            ...$sync,
            'mode' => $forceRefresh ? 'manual_refresh' : 'auto_refresh',
            'synced' => true,
            'queued_analysis_jobs' => $queued,
        ];
    }

    private function dispatchPendingAnalyses(array $articleIds = []): int
    {
        $batchSize = (int) config('services.news_sentiment.analysis_batch_size', 25);
        $query = NewsArticle::query()
            ->where('analysis_status', NewsArticle::STATUS_PENDING)
            ->orderByDesc('published_at')
            ->limit($batchSize);

        if (!empty($articleIds)) {
            $query->whereIn('id', $articleIds);
        }

        $articles = $query->get(['id']);

        foreach ($articles as $article) {
            AnalyzeNewsArticleImpactJob::dispatch($article->id);
        }

        return $articles->count();
    }

    private function buildSummary($rows): array
    {
        if ($rows->isEmpty()) {
            return [
                'total_items' => 0,
                'bullish_count' => 0,
                'bearish_count' => 0,
                'neutral_count' => 0,
                'average_impact_score' => 0,
                'average_confidence_score' => 0,
                'latest_published_at' => null,
            ];
        }

        return [
            'total_items' => $rows->count(),
            'bullish_count' => $rows->where('direction', NewsArticleAssetImpact::DIRECTION_BULLISH)->count(),
            'bearish_count' => $rows->where('direction', NewsArticleAssetImpact::DIRECTION_BEARISH)->count(),
            'neutral_count' => $rows->where('direction', NewsArticleAssetImpact::DIRECTION_NEUTRAL)->count(),
            'average_impact_score' => round($rows->avg('impact_score'), 2),
            'average_confidence_score' => round($rows->avg('confidence_score'), 2),
            'latest_published_at' => optional($rows->first()->published_at)->toIso8601String(),
        ];
    }

    private function formatImpact(NewsArticleAssetImpact $impact): array
    {
        return [
            'id' => $impact->id,
            'asset_symbol' => $impact->asset_symbol,
            'display_name' => $impact->display_name,
            'direction' => $impact->direction,
            'sentiment_label' => $impact->sentiment_label,
            'impact_score' => $impact->impact_score,
            'confidence_score' => $impact->confidence_score,
            'reasoning' => $impact->reasoning,
            'market_theme' => $impact->market_theme,
            'tags' => $impact->tags ?? [],
            'published_at' => optional($impact->published_at)->toIso8601String(),
            'analyzed_at' => optional($impact->analyzed_at)->toIso8601String(),
            'article' => [
                'id' => $impact->article?->id,
                'provider' => $impact->article?->provider,
                'provider_article_id' => $impact->article?->provider_article_id,
                'source_name' => $impact->article?->source_name,
                'title' => $impact->article?->title,
                'summary' => $impact->article?->summary,
                'snippet' => $impact->article?->snippet,
                'url' => $impact->article?->url,
                'image_url' => $impact->article?->image_url,
                'language' => $impact->article?->language,
                'published_at' => optional($impact->article?->published_at)->toIso8601String(),
                'fetched_at' => optional($impact->article?->fetched_at)->toIso8601String(),
                'analysis_status' => $impact->article?->analysis_status,
                'summary_sentiment' => $impact->article?->summary_sentiment,
                'global_impact_score' => $impact->article?->global_impact_score,
                'analyzed_at' => optional($impact->article?->analyzed_at)->toIso8601String(),
            ],
        ];
    }

    private function resolveRequestedAssets(mixed $assets): array
    {
        if ($assets === null || $assets === '') {
            return [];
        }

        $assets = is_array($assets) ? $assets : explode(',', (string) $assets);
        $resolved = [];

        foreach ($assets as $asset) {
            $normalized = TrackedMarketAsset::normalizeAsset($asset);

            if ($normalized) {
                $resolved[] = $normalized;
            }
        }

        return array_values(array_unique($resolved));
    }

    private function resolveStatus(?string $status): string
    {
        return in_array($status, NewsArticle::supportedStatuses(), true)
            ? $status
            : NewsArticle::STATUS_COMPLETED;
    }

    private function resolveDirection(?string $direction): ?string
    {
        return in_array($direction, NewsArticleAssetImpact::supportedDirections(), true)
            ? $direction
            : null;
    }

    private function resolveLimit(mixed $limit): int
    {
        $resolved = (int) $limit;

        if ($resolved < 1) {
            return 20;
        }

        return min($resolved, 100);
    }

    private function resolveScore(mixed $score): ?int
    {
        if ($score === null || $score === '') {
            return null;
        }

        $resolved = (int) $score;

        return max(0, min(100, $resolved));
    }

    private function resolveDate(?string $date, bool $endOfDay = false): ?Carbon
    {
        if (!$date) {
            return null;
        }

        try {
            $parsed = Carbon::parse($date);

            return $endOfDay ? $parsed->endOfDay() : $parsed->startOfDay();
        } catch (\Throwable) {
            throw new RuntimeException('The requested date filter is invalid.');
        }
    }
}
