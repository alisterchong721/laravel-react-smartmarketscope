<?php

namespace App\Http\Service;

use App\Support\TrackedMarketAsset;
use Carbon\Carbon;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use RuntimeException;

class SeasonalityAnalysisService
{
    private const DEFAULT_YEARS = 10;

    public function getSeasonality(array $filters = []): array
    {
        $assets = $this->resolveRequestedAssets($filters['assets'] ?? null);
        $period = $filters['period'] ?? 'monthly';
        $years = max(5, min(30, (int) ($filters['years'] ?? self::DEFAULT_YEARS)));
        $refresh = (bool) ($filters['refresh'] ?? false);

        $items = [];

        foreach ($assets as $asset) {
            $candles = $this->fetchDailyCandles($asset, $years, $refresh);

            if (count($candles) < 2) {
                continue;
            }

            $this->persistDailyCandles($asset, $candles);

            $items[] = [
                'asset_symbol' => $asset,
                'display_name' => TrackedMarketAsset::displayName($asset),
                'monthly' => $this->buildMonthlySeasonality($candles),
                'yearly' => $this->buildYearlyReturns($candles),
            ];
        }

        if (empty($items)) {
            throw new RuntimeException('No seasonality candle data is available for the requested assets.');
        }

        return [
            'period' => $period,
            'items' => $items,
            'meta' => [
                'asset_count' => count($items),
                'years' => $years,
                'source' => [
                    'provider' => 'Frankfurter',
                    'endpoint' => config('services.seasonality.endpoint'),
                ],
            ],
            'available_filters' => [
                'supported_assets' => TrackedMarketAsset::supportedAssets(),
                'default_assets' => TrackedMarketAsset::supportedSymbols(),
                'periods' => ['monthly', 'yearly'],
                'default_years' => self::DEFAULT_YEARS,
            ],
        ];
    }

    private function fetchDailyCandles(string $asset, int $years, bool $refresh = false): array
    {
        $cacheKey = sprintf('seasonality.daily.%s.%s', $asset, $years);

        if ($refresh) {
            Cache::forget($cacheKey);
        }

        return Cache::remember($cacheKey, now()->addDay(), function () use ($asset, $years) {
            $endDate = Carbon::now();
            $startDate = $endDate->copy()->subYears($years)->startOfYear();
            $assetMeta = TrackedMarketAsset::ASSETS[$asset] ?? null;

            if (!$assetMeta) {
                return [];
            }

            $response = Http::timeout((int) config('services.seasonality.timeout', 20))
                ->get(sprintf(
                    '%s/%s..%s',
                    rtrim(config('services.seasonality.endpoint'), '/'),
                    $startDate->toDateString(),
                    $endDate->toDateString()
                ), [
                    'from' => $assetMeta['base_currency'],
                    'to' => $assetMeta['quote_currency'],
                ]);

            if (!$response->ok()) {
                throw new RuntimeException("Unable to fetch seasonality data for {$asset}.");
            }

            return $this->parseRateCandles($response->json(), $assetMeta['quote_currency']);
        });
    }

    private function parseRateCandles(?array $payload, string $quoteCurrency): array
    {
        if (!is_array($payload) || empty($payload['rates']) || !is_array($payload['rates'])) {
            return [];
        }

        $candles = [];

        foreach ($payload['rates'] as $dateValue => $rateSet) {
            if (!isset($rateSet[$quoteCurrency]) || !is_numeric($rateSet[$quoteCurrency])) {
                continue;
            }

            $date = Carbon::parse($dateValue);
            $close = (float) $rateSet[$quoteCurrency];

            $candles[] = [
                'date' => $date->toDateString(),
                'year' => (int) $date->format('Y'),
                'month' => (int) $date->format('n'),
                'open' => $close,
                'close' => $close,
            ];
        }

        usort($candles, fn(array $left, array $right) => strcmp($left['date'], $right['date']));

        return $candles;
    }

    private function buildMonthlySeasonality(array $candles): array
    {
        $byYearMonth = [];

        foreach ($candles as $candle) {
            $key = $candle['year'] . '-' . str_pad((string) $candle['month'], 2, '0', STR_PAD_LEFT);
            $byYearMonth[$key][] = $candle;
        }

        $returnsByMonth = array_fill(1, 12, []);

        foreach ($byYearMonth as $monthCandles) {
            $first = reset($monthCandles);
            $last = end($monthCandles);

            if (!$first || !$last || (float) $first['open'] === 0.0) {
                continue;
            }

            $returnsByMonth[(int) $first['month']][] = [
                'year' => (int) $first['year'],
                'return_percent' => $this->returnPercent((float) $first['open'], (float) $last['close']),
            ];
        }

        $months = [];

        foreach ($returnsByMonth as $month => $returns) {
            $values = array_column($returns, 'return_percent');
            $positiveYears = count(array_filter($values, fn(float $value) => $value > 0));

            $months[] = [
                'month' => $month,
                'month_name' => Carbon::create(null, $month, 1)->format('F'),
                'month_short' => Carbon::create(null, $month, 1)->format('M'),
                'average_return' => $this->roundNullable($this->average($values)),
                'median_return' => $this->roundNullable($this->median($values)),
                'win_rate' => count($values) ? round(($positiveYears / count($values)) * 100, 2) : null,
                'positive_years' => $positiveYears,
                'observations' => count($values),
                'best_year' => $this->bestReturn($returns),
                'worst_year' => $this->worstReturn($returns),
                'history' => $returns,
            ];
        }

        return $months;
    }

    private function buildYearlyReturns(array $candles): array
    {
        $byYear = [];

        foreach ($candles as $candle) {
            $byYear[$candle['year']][] = $candle;
        }

        $returns = [];

        foreach ($byYear as $year => $yearCandles) {
            $first = reset($yearCandles);
            $last = end($yearCandles);

            if (!$first || !$last || (float) $first['open'] === 0.0) {
                continue;
            }

            $returns[] = [
                'year' => (int) $year,
                'return_percent' => $this->returnPercent((float) $first['open'], (float) $last['close']),
                'start_date' => $first['date'],
                'end_date' => $last['date'],
            ];
        }

        return $returns;
    }

    private function persistDailyCandles(string $asset, array $candles): void
    {
        $assetId = $this->assetId($asset);

        if (!$assetId) {
            return;
        }

        $now = now();
        $previousClose = null;
        $rows = [];

        foreach ($candles as $candle) {
            $close = isset($candle['close']) ? (float) $candle['close'] : null;

            if ($close === null) {
                continue;
            }

            $rows[] = [
                'asset_id' => $assetId,
                'period_type' => 'daily',
                'period_date' => $candle['date'],
                'high_price' => $close,
                'low_price' => $close,
                'period_return_percentage' => $previousClose && $previousClose !== 0.0
                    ? $this->returnPercent($previousClose, $close)
                    : null,
                'created_at' => $now,
                'updated_at' => $now,
            ];

            $previousClose = $close;
        }

        if (empty($rows)) {
            return;
        }

        foreach (array_chunk($rows, 500) as $chunk) {
            DB::table('seasonality_data')->upsert(
                $chunk,
                ['asset_id', 'period_type', 'period_date'],
                ['high_price', 'low_price', 'period_return_percentage', 'updated_at']
            );
        }
    }

    private function assetId(string $asset): ?int
    {
        $normalized = TrackedMarketAsset::normalizeAsset($asset);

        if (!$normalized) {
            return null;
        }

        $assetId = DB::table('assets')
            ->where('asset_symbol', $normalized)
            ->value('asset_id');

        return $assetId ? (int) $assetId : null;
    }

    private function resolveRequestedAssets(mixed $assets): array
    {
        if ($assets === null || $assets === '') {
            return TrackedMarketAsset::supportedSymbols();
        }

        $assets = is_array($assets) ? $assets : explode(',', (string) $assets);
        $resolved = [];

        foreach ($assets as $asset) {
            $normalized = TrackedMarketAsset::normalizeAsset($asset);

            if ($normalized) {
                $resolved[] = $normalized;
            }
        }

        return array_values(array_unique($resolved)) ?: TrackedMarketAsset::supportedSymbols();
    }

    private function returnPercent(float $open, float $close): float
    {
        return $this->roundedFloat((($close - $open) / $open) * 100);
    }

    private function average(array $values): ?float
    {
        return count($values) ? array_sum($values) / count($values) : null;
    }

    private function median(array $values): ?float
    {
        $count = count($values);

        if (!$count) {
            return null;
        }

        sort($values);
        $middle = intdiv($count, 2);

        if ($count % 2) {
            return $values[$middle];
        }

        return ($values[$middle - 1] + $values[$middle]) / 2;
    }

    private function bestReturn(array $returns): ?array
    {
        if (empty($returns)) {
            return null;
        }

        usort($returns, fn(array $left, array $right) => $right['return_percent'] <=> $left['return_percent']);

        return $returns[0];
    }

    private function worstReturn(array $returns): ?array
    {
        if (empty($returns)) {
            return null;
        }

        usort($returns, fn(array $left, array $right) => $left['return_percent'] <=> $right['return_percent']);

        return $returns[0];
    }

    private function roundNullable(?float $value): ?float
    {
        return $value === null ? null : $this->roundedFloat($value);
    }

    private function roundedFloat(float $value): float
    {
        return (float) sprintf('%.2F', $value);
    }
}
