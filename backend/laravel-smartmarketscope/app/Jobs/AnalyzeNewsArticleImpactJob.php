<?php

namespace App\Jobs;

use App\Http\Service\OpenAiNewsAnalysisService;
use App\Models\NewsArticle;
use App\Models\NewsArticleAssetImpact;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\DB;
use Throwable;

class AnalyzeNewsArticleImpactJob implements ShouldQueue
{
    use Dispatchable;
    use InteractsWithQueue;
    use Queueable;
    use SerializesModels;

    public int $tries = 3;

    public function __construct(private readonly int $articleId)
    {
    }

    public function handle(OpenAiNewsAnalysisService $analysisService): void
    {
        $article = NewsArticle::query()->find($this->articleId);

        if (!$article) {
            return;
        }

        $result = $analysisService->analyzeArticle($article);

        DB::transaction(function () use ($article, $result): void {
            $article->assetImpacts()->delete();

            foreach ($result['affected_assets'] as $impact) {
                NewsArticleAssetImpact::query()->create([
                    'news_article_id' => $article->id,
                    ...$impact,
                ]);
            }

            $article->update([
                'analysis_status' => NewsArticle::STATUS_COMPLETED,
                'summary_sentiment' => $result['summary_sentiment'],
                'market_theme' => $result['market_theme'],
                'global_impact_score' => $result['global_impact_score'],
                'analyzed_at' => now(),
                'analysis_error' => null,
                'analysis_payload' => $result['raw_analysis'],
            ]);
        });
    }

    public function failed(?Throwable $exception): void
    {
        NewsArticle::query()
            ->whereKey($this->articleId)
            ->update([
                'analysis_status' => NewsArticle::STATUS_FAILED,
                'analysis_error' => $exception?->getMessage(),
                'analyzed_at' => now(),
            ]);
    }
}
