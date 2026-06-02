<?php

namespace App\Support;

class TrackedMarketAsset
{
    public const ASSETS = [
        'EURUSD' => [
            'display_name' => 'Euro / US Dollar',
            'base_currency' => 'EUR',
            'quote_currency' => 'USD',
            'type' => 'forex',
            'keywords' => ['eurusd', 'eur/usd', 'euro', 'ecb', 'eurozone'],
            'entity_symbols' => ['EUR', 'USD'],
            'bullish_definition' => 'Bullish means EUR strengthens relative to USD.',
        ],
        'GBPUSD' => [
            'display_name' => 'British Pound / US Dollar',
            'base_currency' => 'GBP',
            'quote_currency' => 'USD',
            'type' => 'forex',
            'keywords' => ['gbpusd', 'gbp/usd', 'pound', 'sterling', 'boe', 'bank of england', 'uk economy'],
            'entity_symbols' => ['GBP', 'USD'],
            'bullish_definition' => 'Bullish means GBP strengthens relative to USD.',
        ],
        'AUDUSD' => [
            'display_name' => 'Australian Dollar / US Dollar',
            'base_currency' => 'AUD',
            'quote_currency' => 'USD',
            'type' => 'forex',
            'keywords' => ['audusd', 'aud/usd', 'australian dollar', 'rba', 'australia economy'],
            'entity_symbols' => ['AUD', 'USD'],
            'bullish_definition' => 'Bullish means AUD strengthens relative to USD.',
        ],
        'USDCAD' => [
            'display_name' => 'US Dollar / Canadian Dollar',
            'base_currency' => 'USD',
            'quote_currency' => 'CAD',
            'type' => 'forex',
            'keywords' => ['usdcad', 'usd/cad', 'canadian dollar', 'cad', 'boc', 'bank of canada', 'oil', 'crude'],
            'entity_symbols' => ['USD', 'CAD'],
            'bullish_definition' => 'Bullish means USD strengthens relative to CAD.',
        ],
        'USDJPY' => [
            'display_name' => 'US Dollar / Japanese Yen',
            'base_currency' => 'USD',
            'quote_currency' => 'JPY',
            'type' => 'forex',
            'keywords' => ['usdjpy', 'usd/jpy', 'yen', 'boj', 'bank of japan', 'japan economy'],
            'entity_symbols' => ['USD', 'JPY'],
            'bullish_definition' => 'Bullish means USD strengthens relative to JPY.',
        ],
    ];

    public static function supportedAssets(): array
    {
        $assets = [];

        foreach (self::ASSETS as $symbol => $meta) {
            $assets[] = [
                'symbol' => $symbol,
                'display_name' => $meta['display_name'],
                'base_currency' => $meta['base_currency'],
                'quote_currency' => $meta['quote_currency'],
                'type' => $meta['type'],
            ];
        }

        return $assets;
    }

    public static function supportedSymbols(): array
    {
        return array_keys(self::ASSETS);
    }

    public static function normalizeAsset(?string $asset): ?string
    {
        if (!$asset) {
            return null;
        }

        $normalized = strtoupper(str_replace('/', '', trim($asset)));

        return array_key_exists($normalized, self::ASSETS) ? $normalized : null;
    }

    public static function displayName(string $asset): string
    {
        return self::ASSETS[$asset]['display_name'] ?? $asset;
    }

    public static function promptReference(): array
    {
        $reference = [];

        foreach (self::ASSETS as $symbol => $meta) {
            $reference[] = [
                'asset_symbol' => $symbol,
                'display_name' => $meta['display_name'],
                'asset_type' => $meta['type'],
                'bullish_definition' => $meta['bullish_definition'],
                'quote_currency' => $meta['quote_currency'],
                'base_currency' => $meta['base_currency'],
            ];
        }

        return $reference;
    }

    public static function inferRelevantAssets(array $article): array
    {
        $haystack = strtolower(implode(' ', array_filter([
            $article['title'] ?? null,
            $article['description'] ?? null,
            $article['summary'] ?? null,
            $article['snippet'] ?? null,
            $article['keywords'] ?? null,
        ])));

        $entitySymbols = [];

        foreach ($article['entities'] ?? [] as $entity) {
            foreach (['symbol', 'name'] as $key) {
                if (!empty($entity[$key])) {
                    $entitySymbols[] = strtoupper((string) $entity[$key]);
                }
            }
        }

        $matches = [];

        foreach (self::ASSETS as $symbol => $meta) {
            foreach ($meta['keywords'] as $keyword) {
                if (str_contains($haystack, strtolower($keyword))) {
                    $matches[] = $symbol;
                    continue 2;
                }
            }

            foreach ($meta['entity_symbols'] as $entitySymbol) {
                if (in_array($entitySymbol, $entitySymbols, true)) {
                    $matches[] = $symbol;
                    continue 2;
                }
            }
        }

        return array_values(array_unique($matches));
    }
}
