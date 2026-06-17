<?php

namespace App\Http\Service;

use App\Models\CotReport;
use Carbon\Carbon;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\Http;
use RuntimeException;

class CotReportService
{
    public function getCotReport(array $filters = []): array
    {
        $syncStatus = $this->syncLatestData((bool) ($filters['refresh'] ?? false));
        $requestedAssets = $this->resolveRequestedAssets($filters['assets'] ?? ($filters['asset'] ?? null));
        $reportDate = $this->resolveRequestedReportDate($filters['report_date'] ?? null);
        $selectedReportDate = $reportDate?->toDateString();

        if (!$selectedReportDate) {
            $latestStoredDate = CotReport::query()->max('report_date');
            $selectedReportDate = $latestStoredDate ? Carbon::parse($latestStoredDate)->toDateString() : null;
        }

        if (!$selectedReportDate) {
            throw new RuntimeException('No COT data is available in the local database yet.');
        }

        $query = CotReport::query()
            ->when(
                !empty($requestedAssets),
                fn($builder) => $builder->whereIn('asset_symbol', $requestedAssets)
            )
            ->whereDate('report_date', $selectedReportDate)
            ->orderBy('asset_symbol');

        $reports = $query->get();

        if ($reports->isEmpty()) {
            throw new RuntimeException('No COT data is available for the requested filters.');
        }

        $latestDbDate = CotReport::query()->max('report_date');

        return [
            'report_date' => optional($reports->first()->report_date)->toDateString(),
            'latest_stored_report_date' => $latestDbDate ? Carbon::parse($latestDbDate)->toDateString() : null,
            'synced_from_source' => $syncStatus['synced'],
            'sync_mode' => $syncStatus['mode'],
            'items' => $reports->map(fn(CotReport $report) => $this->formatReport($report))->values()->all(),
            'available_filters' => $this->getFiltersMeta(),
            'source' => [
                'provider' => 'CFTC',
                'dataset' => 'Legacy Futures Only Commitments of Traders',
                'endpoint' => config('services.cot_report.endpoint'),
                'latest_source_report_date' => $syncStatus['latest_source_report_date'],
                'latest_stored_report_date' => $latestDbDate ? Carbon::parse($latestDbDate)->toDateString() : null,
            ],
        ];
    }

    public function getFiltersMeta(): array
    {
        $assets = [];

        foreach (CotReport::ASSET_MARKET_MAP as $asset => $meta) {
            $assets[] = [
                'symbol' => $asset,
                'display_name' => $meta['display_name'],
                'base_currency' => $meta['base_currency'],
                'quote_currency' => $meta['quote_currency'],
                'source_market_name' => $meta['market_name'],
                'pair_is_inverse' => $meta['inverse_pair'],
            ];
        }

        return [
            'supported_assets' => $assets,
            'supported_categories' => CotReport::supportedCategories(),
            'default_asset' => CotReport::DEFAULT_ASSETS[0],
        ];
    }

    private function syncLatestData(bool $forceRefresh = false): array
    {
        $latestSourceDate = $this->fetchLatestSourceReportDate();
        $latestStoredDate = CotReport::query()->max('report_date');

        if (!$forceRefresh && $latestStoredDate && Carbon::parse($latestStoredDate)->isSameDay($latestSourceDate)) {
            return [
                'synced' => false,
                'mode' => 'database_only',
                'latest_source_report_date' => $latestSourceDate->toDateString(),
            ];
        }

        $this->syncMissingReports(
            $latestStoredDate ? Carbon::parse($latestStoredDate) : null,
            $forceRefresh
        );

        return [
            'synced' => true,
            'mode' => $latestStoredDate ? 'incremental' : 'full',
            'latest_source_report_date' => $latestSourceDate->toDateString(),
        ];
    }

    private function syncMissingReports(?Carbon $latestStoredDate = null, bool $includeLatestStoredDate = false): void
    {
        $offset = 0;
        $limit = (int) config('services.cot_report.page_size', 1000);

        do {
            $rows = $this->requestSourceRows($latestStoredDate, $limit, $offset, $includeLatestStoredDate);

            if (empty($rows)) {
                break;
            }

            $payload = [];

            foreach ($rows as $row) {
                $normalized = $this->normalizeSourceRow($row);

                if ($normalized) {
                    $payload[] = $normalized;
                }
            }

            if (!empty($payload)) {
                foreach (array_chunk($payload, (int) config('services.cot_report.upsert_batch_size', 100)) as $batch) {
                    CotReport::query()->upsert(
                        $batch,
                        ['asset_symbol', 'report_date'],
                        [
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
                            'updated_at',
                        ]
                    );
                }
            }

            $offset += $limit;
        } while (count($rows) === $limit);
    }

    private function requestSourceRows(?Carbon $latestStoredDate, int $limit, int $offset, bool $includeLatestStoredDate = false): array
    {
        $response = Http::acceptJson()
            ->timeout((int) config('services.cot_report.timeout', 20))
            ->get(config('services.cot_report.endpoint'), [
                '$select' => implode(',', [
                    'id',
                    'market_and_exchange_names',
                    'contract_market_name',
                    'cftc_contract_market_code',
                    'report_date_as_yyyy_mm_dd',
                    'open_interest_all',
                    'noncomm_positions_long_all',
                    'noncomm_positions_short_all',
                    'comm_positions_long_all',
                    'comm_positions_short_all',
                    'nonrept_positions_long_all',
                    'nonrept_positions_short_all',
                    'change_in_noncomm_long_all',
                    'change_in_noncomm_short_all',
                    'change_in_comm_long_all',
                    'change_in_comm_short_all',
                    'change_in_nonrept_long_all',
                    'change_in_nonrept_short_all',
                    'pct_of_oi_noncomm_long_all',
                    'pct_of_oi_noncomm_short_all',
                    'pct_of_oi_comm_long_all',
                    'pct_of_oi_comm_short_all',
                    'pct_of_oi_nonrept_long_all',
                    'pct_of_oi_nonrept_short_all',
                ]),
                '$where' => $this->buildWhereClause($latestStoredDate, $includeLatestStoredDate),
                '$order' => 'report_date_as_yyyy_mm_dd ASC, market_and_exchange_names ASC',
                '$limit' => $limit,
                '$offset' => $offset,
            ]);

        if ($response->failed()) {
            throw new RuntimeException('Unable to fetch COT data from the upstream provider.');
        }

        $payload = $response->json();

        if (!is_array($payload)) {
            throw new RuntimeException('COT provider returned an unexpected response format.');
        }

        return $payload;
    }

    private function fetchLatestSourceReportDate(): Carbon
    {
        $response = Http::acceptJson()
            ->timeout((int) config('services.cot_report.timeout', 20))
            ->get(config('services.cot_report.endpoint'), [
                '$select' => 'report_date_as_yyyy_mm_dd',
                '$order' => 'report_date_as_yyyy_mm_dd DESC',
                '$limit' => 1,
            ]);

        if ($response->failed()) {
            throw new RuntimeException('Unable to fetch the latest COT report date from the upstream provider.');
        }

        $payload = $response->json();
        $rawDate = $payload[0]['report_date_as_yyyy_mm_dd'] ?? null;

        if (!$rawDate) {
            throw new RuntimeException('The upstream COT provider did not return a latest report date.');
        }

        return Carbon::parse($rawDate)->startOfDay();
    }

    private function buildWhereClause(?Carbon $latestStoredDate, bool $includeLatestStoredDate = false): string
    {
        $quotedMarkets = array_map(
            fn(string $market) => "'" . str_replace("'", "\\'", $market) . "'",
            CotReport::marketNames()
        );

        $conditions = [
            "commodity_group_name = 'FINANCIAL INSTRUMENTS'",
            'market_and_exchange_names in(' . implode(',', $quotedMarkets) . ')',
        ];

        if ($latestStoredDate) {
            $operator = $includeLatestStoredDate ? '>=' : '>';
            $conditions[] = "report_date_as_yyyy_mm_dd {$operator} '" . $latestStoredDate->toDateString() . "T00:00:00.000'";
        }

        return implode(' AND ', $conditions);
    }

    private function normalizeSourceRow(array $row): ?array
    {
        $marketMap = CotReport::marketNameToAssetMap();
        $marketName = $row['market_and_exchange_names'] ?? null;
        $assetSymbol = $marketName ? ($marketMap[$marketName] ?? null) : null;

        if (!$assetSymbol) {
            return null;
        }

        $assetMeta = CotReport::ASSET_MARKET_MAP[$assetSymbol];
        $inverse = (bool) $assetMeta['inverse_pair'];
        $reportDate = Carbon::parse($row['report_date_as_yyyy_mm_dd'])->toDateString();

        return [
            'asset_symbol' => $assetSymbol,
            'report_date' => $reportDate,
            'source_market_name' => $marketName,
            'source_contract_market_name' => $row['contract_market_name'] ?? null,
            'source_report_id' => $row['id'] ?? null,
            'source_contract_code' => $row['cftc_contract_market_code'] ?? null,
            'pair_is_inverse' => $inverse,
            'open_interest_all' => $this->toInt($row['open_interest_all'] ?? null),
            'non_commercial_long' => $this->normalizeLongValue($row, 'noncomm_positions_long_all', 'noncomm_positions_short_all', $inverse),
            'non_commercial_short' => $this->normalizeShortValue($row, 'noncomm_positions_long_all', 'noncomm_positions_short_all', $inverse),
            'non_commercial_change_long' => $this->normalizeLongValue($row, 'change_in_noncomm_long_all', 'change_in_noncomm_short_all', $inverse),
            'non_commercial_change_short' => $this->normalizeShortValue($row, 'change_in_noncomm_long_all', 'change_in_noncomm_short_all', $inverse),
            'non_commercial_long_pct' => $this->normalizeLongValue($row, 'pct_of_oi_noncomm_long_all', 'pct_of_oi_noncomm_short_all', $inverse),
            'non_commercial_short_pct' => $this->normalizeShortValue($row, 'pct_of_oi_noncomm_long_all', 'pct_of_oi_noncomm_short_all', $inverse),
            'commercial_long' => $this->normalizeLongValue($row, 'comm_positions_long_all', 'comm_positions_short_all', $inverse),
            'commercial_short' => $this->normalizeShortValue($row, 'comm_positions_long_all', 'comm_positions_short_all', $inverse),
            'commercial_change_long' => $this->normalizeLongValue($row, 'change_in_comm_long_all', 'change_in_comm_short_all', $inverse),
            'commercial_change_short' => $this->normalizeShortValue($row, 'change_in_comm_long_all', 'change_in_comm_short_all', $inverse),
            'commercial_long_pct' => $this->normalizeLongValue($row, 'pct_of_oi_comm_long_all', 'pct_of_oi_comm_short_all', $inverse),
            'commercial_short_pct' => $this->normalizeShortValue($row, 'pct_of_oi_comm_long_all', 'pct_of_oi_comm_short_all', $inverse),
            'nonreportable_long' => $this->normalizeLongValue($row, 'nonrept_positions_long_all', 'nonrept_positions_short_all', $inverse),
            'nonreportable_short' => $this->normalizeShortValue($row, 'nonrept_positions_long_all', 'nonrept_positions_short_all', $inverse),
            'nonreportable_change_long' => $this->normalizeLongValue($row, 'change_in_nonrept_long_all', 'change_in_nonrept_short_all', $inverse),
            'nonreportable_change_short' => $this->normalizeShortValue($row, 'change_in_nonrept_long_all', 'change_in_nonrept_short_all', $inverse),
            'nonreportable_long_pct' => $this->normalizeLongValue($row, 'pct_of_oi_nonrept_long_all', 'pct_of_oi_nonrept_short_all', $inverse),
            'nonreportable_short_pct' => $this->normalizeShortValue($row, 'pct_of_oi_nonrept_long_all', 'pct_of_oi_nonrept_short_all', $inverse),
            'source_payload' => null,
            'created_at' => now(),
            'updated_at' => now(),
        ];
    }

    private function formatReport(CotReport $report): array
    {
        $meta = CotReport::ASSET_MARKET_MAP[$report->asset_symbol];

        return [
            'asset_symbol' => $report->asset_symbol,
            'display_name' => $meta['display_name'],
            'base_currency' => $meta['base_currency'],
            'quote_currency' => $meta['quote_currency'],
            'pair_is_inverse' => $report->pair_is_inverse,
            'report_date' => optional($report->report_date)->toDateString(),
            'open_interest_all' => $report->open_interest_all,
            'source_market_name' => $report->source_market_name,
            'categories' => [
                CotReport::CATEGORY_NON_COMMERCIAL => $this->formatCategory($report, CotReport::CATEGORY_NON_COMMERCIAL),
                CotReport::CATEGORY_COMMERCIAL => $this->formatCategory($report, CotReport::CATEGORY_COMMERCIAL),
                CotReport::CATEGORY_NONREPORTABLE => $this->formatCategory($report, CotReport::CATEGORY_NONREPORTABLE),
            ],
            'primary_chart' => [
                'category' => CotReport::CATEGORY_NON_COMMERCIAL,
                'long_percentage' => (float) $report->non_commercial_long_pct,
                'short_percentage' => (float) $report->non_commercial_short_pct,
            ],
        ];
    }

    private function formatCategory(CotReport $report, string $category): array
    {
        $prefix = $category;
        $longContracts = (int) $report->getAttribute("{$prefix}_long");
        $shortContracts = (int) $report->getAttribute("{$prefix}_short");

        return [
            'long_contracts' => $longContracts,
            'short_contracts' => $shortContracts,
            'change_long_contracts' => (int) $report->getAttribute("{$prefix}_change_long"),
            'change_short_contracts' => (int) $report->getAttribute("{$prefix}_change_short"),
            'long_percentage' => (float) $report->getAttribute("{$prefix}_long_pct"),
            'short_percentage' => (float) $report->getAttribute("{$prefix}_short_pct"),
            'net_position' => $longContracts - $shortContracts,
            'sentiment_bias' => $longContracts >= $shortContracts ? 'long_bias' : 'short_bias',
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
            $normalized = CotReport::normalizeAsset($asset);

            if ($normalized) {
                $resolved[] = $normalized;
            }
        }

        return array_values(array_unique($resolved));
    }

    private function resolveRequestedReportDate(?string $reportDate): ?Carbon
    {
        if (!$reportDate) {
            return null;
        }

        try {
            return Carbon::parse($reportDate)->startOfDay();
        } catch (\Throwable) {
            throw new RuntimeException('The requested report_date is invalid.');
        }
    }

    private function normalizeLongValue(array $row, string $longKey, string $shortKey, bool $inverse): int|float|null
    {
        $value = $inverse ? ($row[$shortKey] ?? null) : ($row[$longKey] ?? null);

        return $this->castSourceValue($value);
    }

    private function normalizeShortValue(array $row, string $longKey, string $shortKey, bool $inverse): int|float|null
    {
        $value = $inverse ? ($row[$longKey] ?? null) : ($row[$shortKey] ?? null);

        return $this->castSourceValue($value);
    }

    private function castSourceValue(mixed $value): int|float|null
    {
        if ($value === null || $value === '') {
            return null;
        }

        return str_contains((string) $value, '.') ? round((float) $value, 2) : (int) $value;
    }

    private function toInt(mixed $value): ?int
    {
        return $value === null || $value === '' ? null : (int) $value;
    }
}
