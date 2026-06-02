<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class NewsArticle extends Model
{
    protected $table = 'sentimental_news';

    public const STATUS_PENDING = 'pending';
    public const STATUS_COMPLETED = 'completed';
    public const STATUS_FAILED = 'failed';

    protected $fillable = [
        'provider',
        'provider_article_id',
        'source_name',
        'title',
        'summary',
        'snippet',
        'url',
        'url_hash',
        'image_url',
        'language',
        'published_at',
        'fetched_at',
        'analysis_status',
        'summary_sentiment',
        'market_theme',
        'global_impact_score',
        'analyzed_at',
        'analysis_error',
        'analysis_payload',
        'raw_payload',
    ];

    protected $casts = [
        'published_at' => 'datetime',
        'fetched_at' => 'datetime',
        'analyzed_at' => 'datetime',
        'analysis_payload' => 'array',
        'raw_payload' => 'array',
    ];

    public function assetImpacts(): HasMany
    {
        return $this->hasMany(NewsArticleAssetImpact::class);
    }

    public static function supportedStatuses(): array
    {
        return [
            self::STATUS_PENDING,
            self::STATUS_COMPLETED,
            self::STATUS_FAILED,
        ];
    }
}
