<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Asset extends Model
{
    protected $primaryKey = 'asset_id';

    protected $fillable = [
        'asset_symbol',
        'asset_name',
        'asset_type',
    ];

    public function newsImpacts(): HasMany
    {
        return $this->hasMany(NewsArticleAssetImpact::class, 'asset_id', 'asset_id');
    }

    public function fundamentalData(): HasMany
    {
        return $this->hasMany(FundamentalData::class, 'asset_id', 'asset_id');
    }
}
