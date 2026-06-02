<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class CotReport extends Model
{
    public const CATEGORY_NON_COMMERCIAL = 'non_commercial';
    public const CATEGORY_COMMERCIAL = 'commercial';
    public const CATEGORY_NONREPORTABLE = 'nonreportable';

    public const DEFAULT_ASSETS = [
        'EURUSD',
        'GBPUSD',
        'AUDUSD',
        'USDCAD',
        'USDJPY',
    ];

    public const ASSET_MARKET_MAP = [
        'EURUSD' => [
            'market_name' => 'EURO FX - CHICAGO MERCANTILE EXCHANGE',
            'display_name' => 'Euro FX',
            'base_currency' => 'EUR',
            'quote_currency' => 'USD',
            'inverse_pair' => false,
        ],
        'GBPUSD' => [
            'market_name' => 'BRITISH POUND - CHICAGO MERCANTILE EXCHANGE',
            'display_name' => 'British Pound',
            'base_currency' => 'GBP',
            'quote_currency' => 'USD',
            'inverse_pair' => false,
        ],
        'AUDUSD' => [
            'market_name' => 'AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE',
            'display_name' => 'Australian Dollar',
            'base_currency' => 'AUD',
            'quote_currency' => 'USD',
            'inverse_pair' => false,
        ],
        'USDCAD' => [
            'market_name' => 'CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE',
            'display_name' => 'Canadian Dollar',
            'base_currency' => 'USD',
            'quote_currency' => 'CAD',
            'inverse_pair' => true,
        ],
        'USDJPY' => [
            'market_name' => 'JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE',
            'display_name' => 'Japanese Yen',
            'base_currency' => 'USD',
            'quote_currency' => 'JPY',
            'inverse_pair' => true,
        ],
    ];

    protected $fillable = [
        'asset_symbol',
        'report_date',
        'source_market_name',
        'source_contract_market_name',
        'source_report_id',
        'source_contract_code',
        'pair_is_inverse',
        'open_interest_all',
        'non_commercial_long',
        'non_commercial_short',
        'non_commercial_change_long',
        'non_commercial_change_short',
        'non_commercial_long_pct',
        'non_commercial_short_pct',
        'commercial_long',
        'commercial_short',
        'commercial_change_long',
        'commercial_change_short',
        'commercial_long_pct',
        'commercial_short_pct',
        'nonreportable_long',
        'nonreportable_short',
        'nonreportable_change_long',
        'nonreportable_change_short',
        'nonreportable_long_pct',
        'nonreportable_short_pct',
        'source_payload',
    ];

    protected $casts = [
        'report_date' => 'date',
        'pair_is_inverse' => 'boolean',
        'non_commercial_long_pct' => 'decimal:2',
        'non_commercial_short_pct' => 'decimal:2',
        'commercial_long_pct' => 'decimal:2',
        'commercial_short_pct' => 'decimal:2',
        'nonreportable_long_pct' => 'decimal:2',
        'nonreportable_short_pct' => 'decimal:2',
        'source_payload' => 'array',
    ];

    public static function supportedAssets(): array
    {
        return array_keys(self::ASSET_MARKET_MAP);
    }

    public static function supportedCategories(): array
    {
        return [
            self::CATEGORY_NON_COMMERCIAL,
            self::CATEGORY_COMMERCIAL,
            self::CATEGORY_NONREPORTABLE,
        ];
    }

    public static function normalizeAsset(?string $asset): ?string
    {
        if (!$asset) {
            return null;
        }

        $normalized = strtoupper(str_replace('/', '', trim($asset)));

        return array_key_exists($normalized, self::ASSET_MARKET_MAP) ? $normalized : null;
    }

    public static function marketNames(): array
    {
        return array_column(self::ASSET_MARKET_MAP, 'market_name');
    }

    public static function marketNameToAssetMap(): array
    {
        $map = [];

        foreach (self::ASSET_MARKET_MAP as $asset => $meta) {
            $map[$meta['market_name']] = $asset;
        }

        return $map;
    }
}
