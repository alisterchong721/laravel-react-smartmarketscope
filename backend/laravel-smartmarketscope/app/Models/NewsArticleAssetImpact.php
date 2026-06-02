<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Support\Facades\DB;

class NewsArticleAssetImpact extends Model
{
    protected $table = 'sentimental_news_asset_impacts';

    public const DIRECTION_BULLISH = 'bullish';
    public const DIRECTION_BEARISH = 'bearish';
    public const DIRECTION_NEUTRAL = 'neutral';

    protected $fillable = [
        'news_article_id',
        'asset_id',
        'asset_symbol',
        'display_name',
        'direction',
        'sentiment_label',
        'impact_score',
        'confidence_score',
        'reasoning',
        'market_theme',
        'tags',
        'provider_entity_sentiment',
        'model_name',
        'published_at',
        'analyzed_at',
        'analysis_payload',
    ];

    protected $casts = [
        'tags' => 'array',
        'analysis_payload' => 'array',
        'published_at' => 'datetime',
        'analyzed_at' => 'datetime',
        'provider_entity_sentiment' => 'decimal:4',
    ];

    public function article(): BelongsTo
    {
        return $this->belongsTo(NewsArticle::class, 'news_article_id');
    }

    public function asset(): BelongsTo
    {
        return $this->belongsTo(Asset::class, 'asset_id', 'asset_id');
    }

    protected static function booted(): void
    {
        static::saving(function (self $impact): void {
            if ($impact->asset_id || !$impact->asset_symbol) {
                return;
            }

            $impact->asset_id = DB::table('assets')
                ->where('asset_symbol', strtoupper((string) $impact->asset_symbol))
                ->value('asset_id');
        });
    }

    public static function supportedDirections(): array
    {
        return [
            self::DIRECTION_BULLISH,
            self::DIRECTION_BEARISH,
            self::DIRECTION_NEUTRAL,
        ];
    }
}
