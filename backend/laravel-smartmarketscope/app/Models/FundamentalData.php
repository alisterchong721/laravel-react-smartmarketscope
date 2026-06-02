<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Support\Facades\DB;

class FundamentalData extends Model
{
    protected $table = 'fundamental_data';
    
    protected $fillable = [
        'asset_id',
        'country',
        'event',
        'currency',
        'actual',
        'actual_raw',
        'actual_source',
        'actual_synced_at',
        'forecast',
        'forecast_raw',
        'previous',
        'previous_raw',
        'impact',
        'importance',
        'date',
        'time',
        'source',
    ];
    
    protected $casts = [
        'date' => 'date',
        'actual' => 'decimal:6',
        'forecast' => 'decimal:6',
        'previous' => 'decimal:6',
        'actual_synced_at' => 'datetime',
    ];

    public function asset(): BelongsTo
    {
        return $this->belongsTo(Asset::class, 'asset_id', 'asset_id');
    }

    protected static function booted(): void
    {
        static::saving(function (self $row): void {
            if ($row->asset_id || !$row->currency) {
                return;
            }

            $assetSymbol = match (strtoupper((string) $row->currency)) {
                'EUR' => 'EURUSD',
                'GBP' => 'GBPUSD',
                'AUD' => 'AUDUSD',
                'CAD' => 'USDCAD',
                'JPY' => 'USDJPY',
                'USD' => 'EURUSD',
                default => null,
            };

            if (!$assetSymbol) {
                return;
            }

            $row->asset_id = DB::table('assets')
                ->where('asset_symbol', $assetSymbol)
                ->value('asset_id');
        });
    }
}
