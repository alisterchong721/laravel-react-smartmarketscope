<?php

namespace App\Http\Service;

use Carbon\Carbon;
use GuzzleHttp\Exception\ClientException;
use GuzzleHttp\Client;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Cache;
use App\Models\FundamentalData;
use Symfony\Component\DomCrawler\Crawler;

class FundamentalScrapeService
{
    private const INVESTING_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36';

    private $client;
    private $apiKey;

    public function __construct()
    {
        $this->client = new Client([
            'timeout' => (int) config('services.forex_factory.timeout', 20),
            'verify' => true,
            'headers' => [
                'User-Agent' => self::INVESTING_USER_AGENT,
                'Accept' => 'application/json,text/html;q=0.9,*/*;q=0.8',
                'Accept-Language' => 'en-US,en;q=0.9',
            ],
        ]);

        $this->apiKey = env('FRED_API_KEY', 'demo');
    }

    /**
     * Get data from FRED API
     */
    public function viewData(string $seriesId, ?string $units = null): array
    {
        try {
            $response = $this->client->get('https://api.stlouisfed.org/fred/series/observations', [
                'query' => [
                    'series_id' => $seriesId,
                    'api_key' => $this->apiKey,
                    'file_type' => 'json',
                    'observation_start' => '2020-01-01',
                    'observation_end' => now()->addMonth()->toDateString(),
                    'sort_order' => 'asc',
                    'units' => $units
                ]
            ]);

            $data = json_decode($response->getBody(), true);


            if (isset($data['observations'])) {
                foreach ($data['observations'] as &$observation) {
                    $observation['value'] = $this->formatNumericValue(
                        $observation['value'] ?? null,
                        $seriesId
                    );
                }
                unset($observation); // Break the reference
            }

            return [
                'success' => true,
                'series_id' => $seriesId,
                'data_count' => $data['count'] ?? 0,
                'observations' => $data['observations'] ?? [],
                'date_range' => '2020-01-01 to ' . now()->addMonth()->toDateString(),
                'units' => $units,
                'formatting' => [
                    'decimal_places' => $this->getDecimalPlaces($seriesId),
                ]

            ];
        } catch (\Exception $e) {
            Log::error('FRED API Error: ' . $e->getMessage());
            return [
                'error' => true,
                'message' => $e->getMessage(),
                'series_id' => $seriesId,
            ];
        }
    }

    /**
     * Store data - handles missing values (.) as NULL
     */
    public function storeData(string $seriesId, string $units): array
    {
        try {
            // 1. Get data from FRED API
            $apiData = $this->viewData($seriesId, $units);

            if (isset($apiData['error'])) {
                return $apiData;
            }

            if (empty($apiData['observations'])) {
                return [
                    'error' => true,
                    'message' => 'No data received from API',
                ];
            }

            $observations = $apiData['observations'];
            $errors = [];
            $processedData = [];

            // 2. Get series configuration
            $seriesConfig = $this->getSeriesConfig($seriesId);
            $eventName = $seriesConfig['event'];
            $releaseTime = $seriesConfig['time'];

            Log::info("Validating " . count($observations) . " observations for {$eventName}");

            // 3. ✅ VALIDATE ALL DATA FIRST (No storage yet)
            foreach ($observations as $index => $observation) {
                $date = $observation['date'] ?? null;

                // Validate date
                if (empty($date)) {
                    $errors[] = "Row {$index}: Date is empty";
                    continue;
                }

                // Validate date format
                if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $date)) {
                    $errors[] = "{$date}: Invalid date format";
                    continue;
                }

                // Handle missing values WITH DECIMAL FORMATTING
                $actual = null;
                $value = $observation['value'] ?? null;

                if ($value === '.') {
                    // Missing value is okay, store as NULL
                    $actual = null;
                } elseif (!is_numeric($value)) {
                    $errors[] = "{$date}: Value '{$value}' is not numeric";
                    continue;
                } else {
                    // ✅ APPLY DECIMAL FORMATTING HERE
                    $actual = $this->formatNumericValue($value, $seriesId);
                }

                // Calculate previous value WITH DECIMAL FORMATTING
                $previous = null;
                if ($index > 0) {
                    $prevObs = $observations[$index - 1];
                    $prevValue = $prevObs['value'] ?? null;
                    if ($prevValue !== '.' && is_numeric($prevValue)) {
                        // ✅ APPLY DECIMAL FORMATTING HERE TOO
                        $previous = $this->formatNumericValue($prevValue, $seriesId);
                    }
                }

                // Calculate impact
                $impact = $this->calculateImpact($seriesId, $actual === null ? null : (float) $actual, $previous === null ? null : (float) $previous);

                // Check for duplicate dates in our validation array
                $duplicate = array_filter($processedData, function ($item) use ($date) {
                    return $item['date'] === $date;
                });

                if (!empty($duplicate)) {
                    $errors[] = "{$date}: Duplicate date in data";
                    continue;
                }

                $processedData[] = [
                    'date' => $date,
                    'actual' => $actual,
                    'previous' => $previous,
                    'impact' => $impact,
                    'valid' => true,
                ];
            }

            // ✅ 4. IF ERRORS FOUND, RETURN THEM AND DON'T STORE ANYTHING
            if (!empty($errors)) {
                Log::error("Validation failed for {$eventName}. Errors: " . implode(', ', $errors));

                return [
                    'error' => true,
                    'message' => 'Data validation failed',
                    'errors' => $errors,
                    'valid_count' => count($processedData),
                    'error_count' => count($errors),
                    'total_observations' => count($observations),
                    'event' => $eventName,
                    'note' => 'No data stored due to validation errors',
                ];
            }

            // ✅ 5. ALL DATA VALID - NOW STORE IN DATABASE
            Log::info("All data validated. Starting database storage for {$eventName}");

            $storedCount = 0;
            $skippedCount = 0;

            // Use database transaction for atomic operation
            \Illuminate\Support\Facades\DB::beginTransaction();

            try {
                foreach ($processedData as $data) {
                    // Check if already exists
                    $exists = FundamentalData::where('event', $eventName)
                        ->where('date', $data['date'])
                        ->exists();

                    if (!$exists) {
                        FundamentalData::create([
                            'country' => 'US',
                            'event' => $eventName,
                            'currency' => 'USD',
                            'actual' => $data['actual'],
                            'forecast' => null,
                            'previous' => $data['previous'],
                            'impact' => $data['impact'],
                            'importance' => 'High',
                            'date' => $data['date'],
                            'time' => $releaseTime,
                            'source' => 'FRED API',
                        ]);

                        $storedCount++;
                        Log::debug("Stored {$eventName}: {$data['date']} with value: {$data['actual']}");
                    } else {
                        $skippedCount++;
                        Log::debug("Skipped existing {$eventName}: {$data['date']}");
                    }
                }

                // Commit transaction
                \Illuminate\Support\Facades\DB::commit();
                Log::info("Successfully stored {$storedCount} records for {$eventName}");
            } catch (\Exception $e) {
                // Rollback transaction on error
                \Illuminate\Support\Facades\DB::rollBack();
                Log::error("Database storage failed for {$eventName}: " . $e->getMessage());

                return [
                    'error' => true,
                    'message' => 'Database storage failed: ' . $e->getMessage(),
                    'event' => $eventName,
                    'note' => 'Transaction rolled back - no data stored',
                ];
            }

            // 6. Return success with decimal info
            $missingCount = count(array_filter($processedData, function ($item) {
                return $item['actual'] === null;
            }));

            return [
                'success' => true,
                'message' => "{$eventName} data stored successfully",
                'stats' => [
                    'stored_new' => $storedCount,
                    'skipped_existing' => $skippedCount,
                    'missing_values' => $missingCount,
                    'total_valid' => count($processedData),
                    'decimal_places' => $this->getDecimalPlaces($seriesId),
                ],
                'event' => $eventName,
                'series_id' => $seriesId,
                'date_range' => '2020-01-01 to ' . now()->addMonth()->toDateString(),
                'transaction' => 'Atomic - all or nothing',
                'data_quality' => [
                    'total_records' => count($processedData),
                    'complete_records' => count($processedData) - $missingCount,
                    'incomplete_records' => $missingCount,
                    'completeness_percentage' => round((count($processedData) - $missingCount) / count($processedData) * 100, 2) . '%',
                ],
                'formatting' => [
                    'decimal_places' => $this->getDecimalPlaces($seriesId),
                    // 'examples' => $this->getFormattingExamples($seriesId),
                ],
                'note' => 'Missing values (.) stored as NULL. Values formatted to appropriate decimal places.',
            ];
        } catch (\Exception $e) {
            Log::error("Failed to store data for {$seriesId}: " . $e->getMessage());
            return [
                'error' => true,
                'message' => $e->getMessage(),
                'note' => 'No data stored due to fatal error',
            ];
        }
    }

    public function syncForexFactoryCalendar(?array $periods = null, ?array $impacts = null): array
    {
        $periods = $periods ?: config('services.forex_factory.periods', ['thisweek', 'nextweek']);
        $impacts = $impacts ?: config('services.forex_factory.impacts', ['High']);
        $allowedImpacts = array_map('strtolower', $impacts);
        $allowedCurrencies = array_map('strtoupper', config('services.forex_factory.currencies', ['USD', 'GBP', 'EUR', 'AUD', 'CAD', 'JPY']));
        $cooldownSeconds = (int) config('services.forex_factory.sync_cooldown_seconds', 900);
        $cacheKey = 'forex_factory_sync:' . md5(json_encode([$periods, $impacts, $allowedCurrencies]));
        $lastSync = Cache::get($cacheKey);

        if ($lastSync && now()->diffInSeconds(Carbon::parse($lastSync)) < $cooldownSeconds) {
            return [
                'success' => true,
                'message' => 'Forex Factory was synced recently. Using stored calendar data to avoid rate limits.',
                'stats' => [
                    'fetched' => 0,
                    'stored_new' => 0,
                    'updated_existing' => 0,
                    'skipped' => 0,
                    'periods' => [],
                    'impacts' => $impacts,
                    'cooldown_seconds' => $cooldownSeconds,
                ],
                'synced_at' => $lastSync,
                'cooldown' => true,
            ];
        }

        $stats = [
            'fetched' => 0,
            'stored_new' => 0,
            'updated_existing' => 0,
            'skipped' => 0,
            'periods' => [],
            'impacts' => $impacts,
        ];

        foreach ($periods as $period) {
            try {
                $events = $this->fetchForexFactoryPeriod($period);
            } catch (ClientException $exception) {
                if ($exception->getResponse()?->getStatusCode() === 404) {
                    $stats['periods'][$period] = 0;
                    $stats['skipped']++;
                    continue;
                }

                if ($exception->getResponse()?->getStatusCode() === 429) {
                    return [
                        'success' => true,
                        'message' => 'Forex Factory rate limit reached. Showing stored calendar data; try syncing again later.',
                        'stats' => $stats,
                        'synced_at' => Cache::get($cacheKey),
                        'rate_limited' => true,
                    ];
                }

                throw $exception;
            }
            $stats['periods'][$period] = count($events);
            $stats['fetched'] += count($events);

            foreach ($events as $event) {
                $importance = trim((string) ($event['impact'] ?? ''));

                if ($importance === '' || strtolower($importance) === 'holiday') {
                    $stats['skipped']++;
                    continue;
                }

                if (!empty($allowedImpacts) && !in_array(strtolower($importance), $allowedImpacts, true)) {
                    $stats['skipped']++;
                    continue;
                }

                $normalized = $this->normalizeForexFactoryEvent($event);

                if (!$normalized) {
                    $stats['skipped']++;
                    continue;
                }

                if (!empty($allowedCurrencies) && !in_array($normalized['currency'], $allowedCurrencies, true)) {
                    $stats['skipped']++;
                    continue;
                }

                $existing = FundamentalData::where('source', 'Forex Factory')
                    ->where('country', $normalized['country'])
                    ->where('event', $normalized['event'])
                    ->where('date', $normalized['date'])
                    ->first();

                if ($existing) {
                    if ($normalized['actual'] === null && $existing->actual !== null && $this->calendarPayloadHasReleased($normalized)) {
                        $normalized['actual'] = $existing->actual;
                        $normalized['actual_raw'] = $existing->actual_raw;
                        $normalized['actual_source'] = $existing->actual_source;
                        $normalized['actual_synced_at'] = $existing->actual_synced_at;
                    } elseif ($normalized['actual'] === null) {
                        $normalized['actual_source'] = null;
                        $normalized['actual_synced_at'] = null;
                    }

                    $normalized['impact'] = $this->calculateCalendarImpact(
                        $normalized['event'],
                        $normalized['actual'] === null ? null : (float) $normalized['actual'],
                        $normalized['forecast'] === null ? null : (float) $normalized['forecast'],
                        $normalized['previous'] === null ? null : (float) $normalized['previous']
                    );

                    $existing->fill($normalized);
                    $existing->save();
                    $stats['updated_existing']++;
                    continue;
                }

                FundamentalData::create($normalized);
                $stats['stored_new']++;
            }
        }

        Cache::put($cacheKey, now()->toIso8601String(), $cooldownSeconds);

        return [
            'success' => true,
            'message' => 'Forex Factory calendar synced successfully',
            'stats' => $stats,
            'synced_at' => now()->toIso8601String(),
        ];
    }

    public function getForexFactoryCalendar(?array $filters = []): array
    {
        $filters = $this->withDefaultCalendarDateRange($filters ?? []);

        $query = FundamentalData::query()
            ->where('source', 'Forex Factory')
            ->whereIn('currency', config('services.forex_factory.currencies', ['USD', 'GBP', 'EUR', 'AUD', 'CAD', 'JPY']))
            ->where(function ($query) {
                $query->whereNotNull('actual')
                    ->orWhereNotNull('actual_raw')
                    ->orWhereNotNull('forecast')
                    ->orWhereNotNull('forecast_raw')
                    ->orWhereNotNull('previous')
                    ->orWhereNotNull('previous_raw');
            })
            ->orderBy('date')
            ->orderBy('time');

        if (!empty($filters['country'])) {
            $query->where('country', $filters['country']);
        }

        if (!empty($filters['currency'])) {
            $query->where('currency', strtoupper($filters['currency']));
        }

        if (!empty($filters['importance'])) {
            $query->where('importance', $filters['importance']);
        }

        if (!empty($filters['start_date'])) {
            $query->whereDate('date', '>=', $filters['start_date']);
        }

        if (!empty($filters['end_date'])) {
            $query->whereDate('date', '<=', $filters['end_date']);
        }

        $limit = min(max((int) ($filters['limit'] ?? 100), 1), 500);

        return $query->limit($limit)->get()->map(fn(FundamentalData $row) => [
            'id' => $row->id,
            'country' => $row->country,
            'currency' => $row->currency,
            'event' => $row->event,
            'importance' => $row->importance,
            'impact' => $row->impact,
            'actual' => $row->actual_raw ?? ($row->actual === null ? null : (float) $row->actual),
            'actual_status' => $this->actualStatus($row),
            'actual_color' => $this->actualColor($row->impact),
            'forecast' => $row->forecast_raw ?? ($row->forecast === null ? null : (float) $row->forecast),
            'previous' => $row->previous_raw ?? ($row->previous === null ? null : (float) $row->previous),
            'actual_source' => $row->actual_source,
            'actual_synced_at' => $row->actual_synced_at?->toIso8601String(),
            'actual_numeric' => $row->actual === null ? null : (float) $row->actual,
            'forecast_numeric' => $row->forecast === null ? null : (float) $row->forecast,
            'previous_numeric' => $row->previous === null ? null : (float) $row->previous,
            'date' => $row->date?->toDateString(),
            'time' => $row->time,
            'source' => $row->source,
            'updated_at' => $row->updated_at?->toIso8601String(),
        ])->all();
    }

    private function withDefaultCalendarDateRange(array $filters): array
    {
        if (!empty($filters['start_date']) || !empty($filters['end_date'])) {
            return $filters;
        }

        $week = now(config('services.forex_factory.timezone', 'Asia/Kuala_Lumpur'));
        $filters['start_date'] = $week->copy()->startOfWeek()->toDateString();
        $filters['end_date'] = $week->copy()->endOfWeek()->toDateString();

        return $filters;
    }

    private function actualStatus(FundamentalData $row): string
    {
        if ($row->actual_raw !== null || $row->actual !== null) {
            return 'released';
        }

        if ($this->isNonNumericCalendarEvent($row->event)) {
            return 'not_applicable';
        }

        return 'pending';
    }

    private function actualColor(?string $impact): string
    {
        return match ($impact) {
            'Bullish' => 'green',
            'Bearish' => 'red',
            default => 'default',
        };
    }

    private function isNonNumericCalendarEvent(string $event): bool
    {
        $event = strtolower($event);

        return str_contains($event, 'speaks')
            || str_contains($event, 'meeting minutes')
            || str_contains($event, 'nomination vote')
            || str_contains($event, 'rate statement')
            || str_contains($event, 'monetary policy statement')
            || str_contains($event, 'press conference');
    }

    public function syncCalendarActuals(?array $countries = null, ?Carbon $startDate = null, ?Carbon $endDate = null): array
    {
        $result = $this->syncInvestingCalendarActuals($countries, $startDate, $endDate);

        if (($result['success'] ?? false) && ($result['stats']['updated_existing'] ?? 0) > 0) {
            return $result;
        }

        $tradingEconomicsApiKey = trim((string) config('services.trading_economics.api_key', ''));

        if ($tradingEconomicsApiKey !== '') {
            $fallback = $this->syncTradingEconomicsActuals($countries, $startDate, $endDate);
            $fallback['fallback_after'] = $result;

            return $fallback;
        }

        return $result;
    }

    public function syncInvestingCalendarActuals(?array $countries = null, ?Carbon $startDate = null, ?Carbon $endDate = null): array
    {
        $startDate = $startDate ?: now()->subDays(7);
        $endDate = $endDate ?: now()->addDays(2);
        $fetchStartDate = $startDate->copy()->subDay();
        $fetchEndDate = $endDate->copy()->addDay();

        try {
            $events = $this->fetchInvestingCalendar($fetchStartDate, $fetchEndDate);
        } catch (ClientException $exception) {
            if (in_array($exception->getResponse()?->getStatusCode(), [403, 429], true)) {
                return [
                    'success' => false,
                    'message' => 'Investing.com temporarily blocked the calendar request. Try again after the cooldown.',
                    'stats' => [
                        'fetched' => 0,
                        'stored_new' => 0,
                        'updated_existing' => 0,
                        'skipped' => 0,
                    ],
                    'synced_at' => now()->toIso8601String(),
                    'blocked' => true,
                ];
            }

            throw $exception;
        }

        $allowedCountries = $countries
            ? array_flip(array_map(fn($country) => $this->normalizeCountryFilter((string) $country), $countries))
            : null;

        $stats = [
            'fetched' => count($events),
            'stored_new' => 0,
            'updated_existing' => 0,
            'skipped' => 0,
        ];

        foreach ($events as $event) {
            if ($allowedCountries && !isset($allowedCountries[$this->normalizeCountryFilter($event['country'])])) {
                $stats['skipped']++;
                continue;
            }

            $result = $this->applyCalendarActual($event, 'Investing.com');

            if ($result === 'updated') {
                $stats['updated_existing']++;
            } elseif ($result === 'created') {
                $stats['stored_new']++;
            } else {
                $stats['skipped']++;
            }
        }

        $detailPageStats = $this->syncInvestingEventPageActuals($countries, $startDate, $endDate);

        $stats['fetched'] += $detailPageStats['fetched'];
        $stats['updated_existing'] += $detailPageStats['updated_existing'];
        $stats['skipped'] += $detailPageStats['skipped'];

        return [
            'success' => true,
            'message' => 'Investing.com actual, forecast, and previous values synced into calendar rows',
            'stats' => $stats,
            'detail_page_stats' => $detailPageStats,
            'synced_at' => now()->toIso8601String(),
        ];
    }

    private function syncInvestingEventPageActuals(?array $countries, Carbon $startDate, Carbon $endDate): array
    {
        $pages = config('services.investing_calendar.event_pages', []);
        $allowedCountries = $countries
            ? array_flip(array_map(fn($country) => $this->normalizeCountryFilter((string) $country), $countries))
            : null;

        $stats = [
            'fetched' => 0,
            'updated_existing' => 0,
            'skipped' => 0,
        ];

        foreach ($pages as $country => $eventPages) {
            $country = $this->normalizeCountryFilter((string) $country);

            if ($allowedCountries && !isset($allowedCountries[$country])) {
                continue;
            }

            foreach ($eventPages as $eventKey => $url) {
                $row = FundamentalData::where('source', 'Forex Factory')
                    ->where('country', $country)
                    ->whereBetween('date', [$startDate->toDateString(), $endDate->toDateString()])
                    ->whereNull('actual')
                    ->whereNull('actual_raw')
                    ->get()
                    ->first(fn(FundamentalData $row) => $this->canonicalCalendarEventKey($row->event) === $this->canonicalCalendarEventKey((string) $eventKey));

                if (!$row) {
                    continue;
                }

                $stats['fetched']++;

                if (!$this->calendarRowHasReleased($row)) {
                    $stats['skipped']++;
                    continue;
                }

                try {
                    $event = $this->fetchInvestingEventPageActual((string) $url, $country, $row->event, $row->date->toDateString(), $row->time);
                } catch (\Throwable $exception) {
                    Log::warning('Investing.com event page actual fallback failed', [
                        'country' => $country,
                        'event' => $row->event,
                        'url' => $url,
                        'message' => $exception->getMessage(),
                    ]);

                    $stats['skipped']++;
                    continue;
                }

                if (!$event) {
                    $stats['skipped']++;
                    continue;
                }

                $result = $this->applyCalendarActual($event, 'Investing.com');

                if ($result === 'updated') {
                    $stats['updated_existing']++;
                } else {
                    $stats['skipped']++;
                }
            }
        }

        return $stats;
    }

    private function fetchInvestingEventPageActual(string $url, string $country, string $event, string $date, ?string $time = null): ?array
    {
        $response = $this->client->get($url, [
            'timeout' => (int) config('services.investing_calendar.timeout', 20),
            'headers' => [
                'User-Agent' => self::INVESTING_USER_AGENT,
                'Accept' => 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language' => 'en-US,en;q=0.9',
                'Referer' => 'https://www.investing.com/economic-calendar',
            ],
        ]);

        return $this->parseInvestingEventPageActual(
            (string) $response->getBody(),
            $country,
            $event,
            $date,
            $time
        );
    }

    public function syncTradingEconomicsActuals(?array $countries = null, ?Carbon $startDate = null, ?Carbon $endDate = null): array
    {
        $apiKey = trim((string) config('services.trading_economics.api_key', ''));

        if ($apiKey === '') {
            return [
                'success' => false,
                'message' => 'TRADING_ECONOMICS_API_KEY is missing. Forex Factory export has no actual values, so actual sync needs this provider key.',
                'stats' => [
                    'fetched' => 0,
                    'updated_existing' => 0,
                    'skipped' => 0,
                ],
            ];
        }

        $countries = $countries ?: config('services.trading_economics.countries', []);
        $startDate = $startDate ?: now()->subDays(7);
        $endDate = $endDate ?: now()->addDays(2);

        $stats = [
            'fetched' => 0,
            'stored_new' => 0,
            'updated_existing' => 0,
            'skipped' => 0,
            'countries' => [],
        ];

        foreach ($countries as $country) {
            $events = $this->fetchTradingEconomicsCalendar($country, $apiKey, $startDate, $endDate);
            $stats['countries'][$country] = count($events);
            $stats['fetched'] += count($events);

            foreach ($events as $event) {
                $result = $this->applyTradingEconomicsActual($event);

                if ($result === 'updated') {
                    $stats['updated_existing']++;
                } elseif ($result === 'created') {
                    $stats['stored_new']++;
                } else {
                    $stats['skipped']++;
                }
            }
        }

        return [
            'success' => true,
            'message' => 'Trading Economics actual values synced into existing Forex Factory calendar rows',
            'stats' => $stats,
            'synced_at' => now()->toIso8601String(),
        ];
    }

    public function importForexFactoryCsv(string $path): array
    {
        if (!is_readable($path)) {
            throw new \InvalidArgumentException("CSV file is not readable: {$path}");
        }

        $handle = fopen($path, 'r');

        if (!$handle) {
            throw new \RuntimeException("Unable to open CSV file: {$path}");
        }

        $headers = fgetcsv($handle);

        if (!$headers) {
            fclose($handle);
            throw new \RuntimeException('CSV file is empty or missing a header row.');
        }

        $headers = array_map(fn($header) => strtolower(trim((string) $header)), $headers);
        $stats = [
            'read' => 0,
            'stored_new' => 0,
            'updated_existing' => 0,
            'skipped' => 0,
        ];

        while (($values = fgetcsv($handle)) !== false) {
            $stats['read']++;
            $row = [];

            foreach ($headers as $index => $header) {
                $row[$header] = $values[$index] ?? null;
            }

            $normalized = $this->normalizeForexFactoryCsvRow($row);

            if (!$normalized || $normalized['actual'] === null) {
                $stats['skipped']++;
                continue;
            }

            $existing = FundamentalData::where('source', 'Forex Factory')
                ->where('country', $normalized['country'])
                ->where('event', $normalized['event'])
                ->where('date', $normalized['date'])
                ->where('time', $normalized['time'])
                ->first();

            if ($existing) {
                $existing->fill($normalized);
                $existing->save();
                $stats['updated_existing']++;
                continue;
            }

            FundamentalData::create($normalized);
            $stats['stored_new']++;
        }

        fclose($handle);

        return [
            'success' => true,
            'message' => 'Forex Factory CSV imported successfully',
            'stats' => $stats,
            'imported_at' => now()->toIso8601String(),
        ];
    }

    private function fetchForexFactoryPeriod(string $period): array
    {
        $safePeriod = preg_replace('/[^a-z]/', '', strtolower($period));
        $baseUrl = rtrim((string) config('services.forex_factory.endpoint_base', 'https://nfs.faireconomy.media'), '/');
        $url = "{$baseUrl}/ff_calendar_{$safePeriod}.json";

        $response = $this->client->get($url);
        $payload = json_decode((string) $response->getBody(), true);

        if (!is_array($payload)) {
            throw new \RuntimeException("Forex Factory returned invalid JSON for {$period}.");
        }

        return $payload;
    }

    private function fetchInvestingCalendar(Carbon $startDate, Carbon $endDate): array
    {
        $events = [];
        $seen = [];
        $importances = config('services.investing_calendar.importances', [1, 2, 3]);

        foreach ($importances as $importance) {
            $responseBody = $this->postInvestingCalendarRequest((int) $importance, $startDate, $endDate);

            $payload = json_decode($responseBody, true);

            if (!is_array($payload) || !isset($payload['data'])) {
                throw new \RuntimeException('Investing.com returned invalid calendar data.');
            }

            foreach ($this->parseInvestingCalendarRows((string) $payload['data'], (int) $importance) as $event) {
                $key = implode('|', [
                    $event['country'],
                    $event['date'],
                    $event['event'],
                    $event['actual_raw'],
                    $event['forecast_raw'],
                    $event['previous_raw'],
                ]);

                if (isset($seen[$key])) {
                    continue;
                }

                $seen[$key] = true;
                $events[] = $event;
            }
        }

        return $events;
    }

    private function postInvestingCalendarRequest(int $importance, Carbon $startDate, Carbon $endDate): string
    {
        $endpoint = (string) config('services.investing_calendar.endpoint');
        $timeout = (int) config('services.investing_calendar.timeout', 20);
        $formParams = $this->investingCalendarFormParams($importance, $startDate, $endDate);

        try {
            $response = $this->client->post($endpoint, [
                'timeout' => $timeout,
                'headers' => $this->investingCalendarHeaders(),
                'form_params' => $formParams,
                'curl' => [
                    CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_2_0,
                ],
            ]);

            return (string) $response->getBody();
        } catch (ClientException $exception) {
            if ($exception->getResponse()?->getStatusCode() !== 403) {
                throw $exception;
            }

            Log::warning('Investing Guzzle request blocked; retrying with native cURL', [
                'status' => $exception->getResponse()?->getStatusCode(),
                'body' => substr((string) $exception->getResponse()?->getBody(), 0, 500),
            ]);

            return $this->postInvestingCalendarWithCurl($endpoint, $timeout, $formParams);
        }
    }

    private function postInvestingCalendarWithCurl(string $endpoint, int $timeout, array $formParams): string
    {
        $handle = curl_init($endpoint);

        if ($handle === false) {
            throw new \RuntimeException('Unable to initialize Investing.com cURL request.');
        }

        curl_setopt_array($handle, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => http_build_query($formParams),
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => $timeout,
            CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_2_0,
            CURLOPT_HTTPHEADER => array_map(
                fn(string $name, string $value) => "{$name}: {$value}",
                array_keys($this->investingCalendarHeaders()),
                $this->investingCalendarHeaders()
            ),
        ]);

        $responseBody = curl_exec($handle);
        $statusCode = (int) curl_getinfo($handle, CURLINFO_RESPONSE_CODE);
        $error = curl_error($handle);
        curl_close($handle);

        if ($responseBody === false || $statusCode >= 400) {
            throw new \RuntimeException("Investing.com cURL request failed with status {$statusCode}: {$error}");
        }

        return (string) $responseBody;
    }

    private function investingCalendarHeaders(): array
    {
        return [
            'User-Agent' => self::INVESTING_USER_AGENT,
            'Accept' => 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language' => 'en-US,en;q=0.9',
            'Content-Type' => 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With' => 'XMLHttpRequest',
            'Origin' => 'https://www.investing.com',
            'Referer' => 'https://www.investing.com/economic-calendar',
        ];
    }

    private function investingCalendarFormParams(int $importance, Carbon $startDate, Carbon $endDate): array
    {
        return [
            'importance[]' => $importance,
            'timeZone' => (int) config('services.investing_calendar.timezone', 8),
            'timeFilter' => 'timeRemain',
            'currentTab' => 'custom',
            'dateFrom' => $startDate->format('Y-m-d'),
            'dateTo' => $endDate->format('Y-m-d'),
            'limit_from' => 0,
        ];
    }

    private function parseInvestingCalendarRows(string $html, ?int $importance = null): array
    {
        $crawler = new Crawler('<table><tbody>' . $html . '</tbody></table>');
        $events = [];
        $currentDate = null;

        $crawler->filter('tr')->each(function (Crawler $row) use (&$events, &$currentDate, $importance) {
            if ($row->filter('.theDay')->count() > 0) {
                $currentDate = trim($row->filter('.theDay')->text(''));
                return;
            }

            if (!$row->attr('data-event-datetime')) {
                return;
            }

            $eventName = trim(preg_replace('/\s+/', ' ', $row->filter('td.event')->text('')));
            $countryCell = trim(preg_replace('/\s+/', ' ', $row->filter('td.flagCur')->text('')));
            $actualRaw = $this->normalizeRawCalendarValue($row->filter('td.act')->text(''));
            $forecastRaw = $this->normalizeRawCalendarValue($row->filter('td.fore')->text(''));
            $previousRaw = $this->normalizeRawCalendarValue($row->filter('td.prev')->text(''));

            if ($eventName === '' || $countryCell === '') {
                return;
            }

            $actual = $this->parseCalendarNumber($actualRaw);
            $forecast = $this->parseCalendarNumber($forecastRaw);
            $previous = $this->parseCalendarNumber($previousRaw);

            if ($actual === null && $forecast === null && $previous === null) {
                return;
            }

            $events[] = [
                'country' => $this->investingCountryToLocal($countryCell),
                'event' => $eventName,
                'actual_raw' => $actualRaw,
                'actual' => $actual,
                'forecast_raw' => $forecastRaw,
                'forecast' => $forecast,
                'previous_raw' => $previousRaw,
                'previous' => $previous,
                'importance' => $this->calendarImportanceLabel($importance),
                'date' => Carbon::parse((string) $row->attr('data-event-datetime'))->toDateString(),
                'time' => Carbon::parse((string) $row->attr('data-event-datetime'))->format('H:i:s'),
                'current_date' => $currentDate,
            ];
        });

        return $events;
    }

    private function parseInvestingEventPageActual(string $html, string $country, string $event, string $date, ?string $time = null): ?array
    {
        if ($time !== null && !$this->calendarDateTimeHasReleased($date, $time)) {
            return null;
        }

        $crawler = new Crawler($html);
        $text = preg_replace('/\s+/', ' ', $crawler->filter('body')->text('', false));
        $targetDate = Carbon::parse($date);
        $dateLabels = array_values(array_unique([
            $targetDate->format('M j, Y'),
            $targetDate->copy()->subDay()->format('M j, Y'),
        ]));
        $values = null;

        foreach ($dateLabels as $dateLabel) {
            if (!preg_match('/' . preg_quote($dateLabel, '/') . '\s*(?:\([^)]*\))?\s*\d{2}:\d{2}\s*(.*?)(?=\s+[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\s*(?:\(|\d{2}:\d{2})|\s+Show More|\z)/', (string) $text, $match)) {
                continue;
            }

            preg_match_all('/[-+]?\d+(?:[.,]\d+)?(?:[KMBT%])?/i', $match[1], $matchedValues);
            $values = $matchedValues[0] ?? [];
            break;
        }

        if ($values === null) {
            foreach ($dateLabels as $dateLabel) {
                if (!preg_match('/Latest Release\s*' . preg_quote($dateLabel, '/') . '.*?Actual\s*([-+]?\d+(?:[.,]\d+)?(?:[KMBT%])?).*?Forecast\s*([-+]?\d+(?:[.,]\d+)?(?:[KMBT%])?).*?Previous\s*([-+]?\d+(?:[.,]\d+)?(?:[KMBT%])?)/i', (string) $text, $summaryMatch)) {
                    continue;
                }

                $values = array_slice($summaryMatch, 1, 3);
                break;
            }
        }

        $values = $values ?? [];

        if (count($values) < 3) {
            return null;
        }

        $actualRaw = $this->normalizeRawCalendarValue($values[0]);
        $forecastRaw = $this->normalizeRawCalendarValue($values[1]);
        $previousRaw = $this->normalizeRawCalendarValue($values[2]);
        $actual = $this->parseCalendarNumber($actualRaw);

        if ($actual === null) {
            return null;
        }

        return [
            'country' => $country,
            'event' => $event,
            'actual_raw' => $actualRaw,
            'actual' => $actual,
            'forecast_raw' => $forecastRaw,
            'forecast' => $this->parseCalendarNumber($forecastRaw),
            'previous_raw' => $previousRaw,
            'previous' => $this->parseCalendarNumber($previousRaw),
            'importance' => 'High',
            'date' => $targetDate->toDateString(),
            'time' => $time,
        ];
    }

    private function applyCalendarActual(array $event, string $actualSource): string|false
    {
        if (empty($event['date']) || empty($event['event']) || empty($event['country'])) {
            return false;
        }

        if (($event['actual'] ?? null) === null && ($event['forecast'] ?? null) === null && ($event['previous'] ?? null) === null) {
            return false;
        }

        $eventKey = $this->canonicalCalendarEventKey((string) $event['event']);

        if ($eventKey === '') {
            return false;
        }

        $row = $this->findCalendarActualTargetRow('Forex Factory', (string) $event['country'], (string) $event['date'], $eventKey);

        if (!$row) {
            $row = $this->findCalendarActualTargetRow($actualSource, (string) $event['country'], (string) $event['date'], $eventKey);
        }

        if (!$row) {
            $currency = $this->countryToCurrency((string) $event['country']);
            $allowedCurrencies = array_map('strtoupper', config('services.forex_factory.currencies', ['USD', 'GBP', 'EUR', 'AUD', 'CAD', 'JPY']));
            $trackedEventKeys = [
                'interest rate',
                'cpi mom',
                'cpi yoy',
                'core cpi mom',
                'core cpi yoy',
                'trimmed mean cpi mom',
                'trimmed mean cpi yoy',
                'median cpi yoy',
                'tokyo core cpi yoy',
                'national core cpi yoy',
                'unemployment rate',
                'employment change',
                'average hourly earnings',
                'average earnings',
                'non farm payrolls',
                'adp non farm employment change',
                'job openings',
                'gdp mom',
                'gdp qoq',
                'retail sales mom',
                'core retail sales mom',
                'manufacturing pmi',
                'services pmi',
                'claimant count change',
                'wage price index',
                'monetary policy statement',
                'rate statement',
            ];

            if (!in_array($currency, $allowedCurrencies, true)
                || ($event['importance'] ?? 'High') !== 'High'
                || !in_array($eventKey, $trackedEventKeys, true)
            ) {
                return false;
            }

            FundamentalData::create([
                'country' => $event['country'],
                'event' => $this->normalizeProviderEventTitle((string) $event['event'], (string) $event['country']),
                'currency' => $currency,
                'actual' => $event['actual'] ?? null,
                'actual_raw' => $this->normalizeRawCalendarValue($event['actual_raw'] ?? null),
                'actual_source' => ($event['actual'] ?? null) === null ? null : $actualSource,
                'actual_synced_at' => ($event['actual'] ?? null) === null ? null : now(),
                'forecast' => $event['forecast'] ?? null,
                'forecast_raw' => $this->normalizeRawCalendarValue($event['forecast_raw'] ?? null),
                'previous' => $event['previous'] ?? null,
                'previous_raw' => $this->normalizeRawCalendarValue($event['previous_raw'] ?? null),
                'impact' => $this->calculateCalendarImpact(
                    (string) $event['event'],
                    ($event['actual'] ?? null) === null ? null : (float) $event['actual'],
                    ($event['forecast'] ?? null) === null ? null : (float) $event['forecast'],
                    ($event['previous'] ?? null) === null ? null : (float) $event['previous'],
                ),
                'importance' => $event['importance'] ?? 'High',
                'date' => $event['date'],
                'time' => empty($event['time'])
                    ? Carbon::parse((string) $event['date'])->format('H:i:s')
                    : (string) $event['time'],
                'source' => $actualSource,
            ]);

            return 'created';
        }

        $hasReleased = $this->calendarRowHasReleased($row);
        $actual = ($event['actual'] ?? null) === null
            ? ($hasReleased && $row->actual !== null ? (float) $row->actual : null)
            : (float) $event['actual'];
        $forecast = ($event['forecast'] ?? null) === null ? ($row->forecast === null ? null : (float) $row->forecast) : (float) $event['forecast'];
        $previous = ($event['previous'] ?? null) === null ? ($row->previous === null ? null : (float) $row->previous) : (float) $event['previous'];

        $updates = [
            'impact' => $this->calculateCalendarImpact(
                $row->event,
                $actual,
                $forecast,
                $previous
            ),
        ];

        if (($event['actual'] ?? null) !== null) {
            $updates['actual'] = $event['actual'];
            $updates['actual_raw'] = $this->normalizeRawCalendarValue($event['actual_raw'] ?? $event['actual']);
            $updates['actual_source'] = $actualSource;
            $updates['actual_synced_at'] = now();
        } elseif (!$hasReleased) {
            $updates['actual'] = null;
            $updates['actual_raw'] = null;
            $updates['actual_source'] = null;
            $updates['actual_synced_at'] = null;
        }

        if (($event['forecast'] ?? null) !== null) {
            $updates['forecast'] = $event['forecast'];
            $updates['forecast_raw'] = $this->normalizeRawCalendarValue($event['forecast_raw'] ?? $event['forecast']);
        }

        if (($event['previous'] ?? null) !== null) {
            $updates['previous'] = $event['previous'];
            $updates['previous_raw'] = $this->normalizeRawCalendarValue($event['previous_raw'] ?? $event['previous']);
        }

        $row->fill($updates);
        $row->save();

        return 'updated';
    }

    private function findCalendarActualTargetRow(string $source, string $country, string $date, string $eventKey): ?FundamentalData
    {
        $exact = FundamentalData::where('source', $source)
            ->where('country', $country)
            ->whereDate('date', $date)
            ->get()
            ->first(fn(FundamentalData $row) => $this->canonicalCalendarEventKey($row->event) === $eventKey);

        if ($exact) {
            return $exact;
        }

        $targetDate = Carbon::parse($date);
        $candidates = FundamentalData::where('source', $source)
            ->where('country', $country)
            ->whereBetween('date', [
                $targetDate->copy()->subDay()->toDateString(),
                $targetDate->copy()->addDay()->toDateString(),
            ])
            ->get()
            ->filter(fn(FundamentalData $row) => $this->canonicalCalendarEventKey($row->event) === $eventKey)
            ->values();

        if ($candidates->count() === 1) {
            return $candidates->first();
        }

        $pending = $candidates
            ->filter(fn(FundamentalData $row) => $row->actual === null && $row->actual_raw === null)
            ->values();

        return $pending->count() === 1 ? $pending->first() : null;
    }

    private function fetchTradingEconomicsCalendar(string $country, string $apiKey, Carbon $startDate, Carbon $endDate): array
    {
        $baseUrl = rtrim((string) config('services.trading_economics.endpoint_base', 'https://api.tradingeconomics.com'), '/');
        $safeCountry = rawurlencode(strtolower($country));
        $response = $this->client->get("{$baseUrl}/calendar/country/{$safeCountry}", [
            'timeout' => (int) config('services.trading_economics.timeout', 20),
            'query' => [
                'c' => $apiKey,
                'd1' => $startDate->toDateString(),
                'd2' => $endDate->toDateString(),
                'importance' => 3,
                'values' => 'true',
                'f' => 'json',
            ],
        ]);

        $payload = json_decode((string) $response->getBody(), true);

        if (!is_array($payload)) {
            throw new \RuntimeException("Trading Economics returned invalid JSON for {$country}.");
        }

        return $payload;
    }

    private function applyTradingEconomicsActual(array $event): string|false
    {
        $actualRaw = $this->firstArrayValue($event, ['Actual', 'actual']);
        $numericActual = $this->firstArrayValue($event, ['ActualValue', 'actualValue', 'actual_value']);
        $actual = $this->parseCalendarNumber($numericActual ?? $actualRaw);

        if ($actualRaw === null || $actual === null) {
            return false;
        }

        $dateValue = $this->firstArrayValue($event, ['Date', 'date']);
        $eventName = $this->firstArrayValue($event, ['Event', 'Category', 'event', 'category']);
        $countryName = $this->firstArrayValue($event, ['Country', 'country']);

        if (!$dateValue || !$eventName || !$countryName) {
            return false;
        }

        $releasedAt = Carbon::parse((string) $dateValue)->setTimezone(config('app.timezone'));
        $country = $this->tradingEconomicsCountryToLocal((string) $countryName);
        $eventKey = $this->canonicalCalendarEventKey((string) $eventName);

        if ($eventKey === '') {
            return false;
        }

        return $this->applyCalendarActual([
            'country' => $country,
            'event' => (string) $eventName,
            'actual' => $actual,
            'actual_raw' => $this->normalizeRawCalendarValue($actualRaw),
            'date' => $releasedAt->toDateString(),
        ], 'Trading Economics');
    }

    private function firstArrayValue(array $row, array $keys)
    {
        foreach ($keys as $key) {
            if (array_key_exists($key, $row) && trim((string) $row[$key]) !== '') {
                return $row[$key];
            }
        }

        return null;
    }

    private function normalizeForexFactoryCsvRow(array $row): ?array
    {
        $title = $this->firstCsvValue($row, ['title', 'event', 'name']);
        $currency = strtoupper((string) $this->firstCsvValue($row, ['country', 'currency', 'currency code']));
        $impact = $this->firstCsvValue($row, ['impact', 'importance']);
        $actualRaw = $this->firstCsvValue($row, ['actual']);
        $forecastRaw = $this->firstCsvValue($row, ['forecast']);
        $previousRaw = $this->firstCsvValue($row, ['previous', 'prev']);
        $dateValue = $this->firstCsvValue($row, ['date', 'datetime', 'time']);
        $timeValue = $this->firstCsvValue($row, ['time']);

        if (!$title || !$currency || !$dateValue) {
            return null;
        }

        $dateString = trim((string) $dateValue);

        if ($timeValue && !preg_match('/\d{1,2}:\d{2}/', $dateString)) {
            $dateString .= ' ' . trim((string) $timeValue);
        }

        $releasedAt = Carbon::parse($dateString)->setTimezone(config('services.forex_factory.timezone', 'Asia/Kuala_Lumpur'));
        $actual = $this->parseCalendarNumber($actualRaw);
        $forecast = $this->parseCalendarNumber($forecastRaw);
        $previous = $this->parseCalendarNumber($previousRaw);

        return [
            'country' => $this->currencyToCountry($currency),
            'event' => $this->normalizeForexFactoryTitle(trim((string) $title), $currency),
            'currency' => $currency,
            'actual' => $actual,
            'actual_raw' => $this->normalizeRawCalendarValue($actualRaw),
            'forecast' => $forecast,
            'forecast_raw' => $this->normalizeRawCalendarValue($forecastRaw),
            'previous' => $previous,
            'previous_raw' => $this->normalizeRawCalendarValue($previousRaw),
            'impact' => $this->calculateCalendarImpact((string) $title, $actual, $forecast, $previous),
            'importance' => $impact ? trim((string) $impact) : 'High',
            'date' => $releasedAt->toDateString(),
            'time' => $releasedAt->format('H:i:s'),
            'source' => 'Forex Factory',
        ];
    }

    private function firstCsvValue(array $row, array $keys): ?string
    {
        foreach ($keys as $key) {
            $normalizedKey = strtolower($key);

            if (array_key_exists($normalizedKey, $row) && trim((string) $row[$normalizedKey]) !== '') {
                return trim((string) $row[$normalizedKey]);
            }
        }

        return null;
    }

    private function normalizeForexFactoryEvent(array $event): ?array
    {
        $currency = strtoupper(trim((string) ($event['country'] ?? '')));
        $title = trim((string) ($event['title'] ?? ''));
        $date = trim((string) ($event['date'] ?? ''));

        if ($currency === '' || $title === '' || $date === '') {
            return null;
        }

        $releasedAt = Carbon::parse($date)->setTimezone(config('services.forex_factory.timezone', 'Asia/Kuala_Lumpur'));
        $actual = $this->parseCalendarNumber($event['actual'] ?? null);
        $forecast = $this->parseCalendarNumber($event['forecast'] ?? null);
        $previous = $this->parseCalendarNumber($event['previous'] ?? null);

        return [
            'country' => $this->currencyToCountry($currency),
            'event' => $this->normalizeForexFactoryTitle($title, $currency),
            'currency' => $currency,
            'actual' => $actual,
            'actual_raw' => $this->normalizeRawCalendarValue($event['actual'] ?? null),
            'forecast' => $forecast,
            'forecast_raw' => $this->normalizeRawCalendarValue($event['forecast'] ?? null),
            'previous' => $previous,
            'previous_raw' => $this->normalizeRawCalendarValue($event['previous'] ?? null),
            'impact' => $this->calculateCalendarImpact($title, $actual, $forecast, $previous),
            'importance' => trim((string) ($event['impact'] ?? '')),
            'date' => $releasedAt->toDateString(),
            'time' => $releasedAt->format('H:i:s'),
            'source' => 'Forex Factory',
        ];
    }

    private function calendarPayloadHasReleased(array $event): bool
    {
        if (empty($event['date'])) {
            return false;
        }

        return $this->calendarDateTimeHasReleased(
            (string) $event['date'],
            empty($event['time']) ? '00:00:00' : (string) $event['time']
        );
    }

    private function calendarRowHasReleased(FundamentalData $row): bool
    {
        if (!$row->date) {
            return false;
        }

        return $this->calendarDateTimeHasReleased(
            $row->date->toDateString(),
            empty($row->time) ? '00:00:00' : (string) $row->time
        );
    }

    private function calendarDateTimeHasReleased(string $date, string $time): bool
    {
        $timezone = config('services.forex_factory.timezone', 'Asia/Kuala_Lumpur');
        $time = trim($time) === '' ? '00:00:00' : trim($time);
        $releasedAt = Carbon::parse(trim($date) . ' ' . $time, $timezone);

        return now($timezone)->greaterThanOrEqualTo($releasedAt);
    }

    private function normalizeRawCalendarValue($value): ?string
    {
        if ($value === null) {
            return null;
        }

        $value = trim(str_replace("\xc2\xa0", ' ', (string) $value));

        return $value === '' ? null : $value;
    }

    private function normalizeForexFactoryTitle(string $title, string $currency): string
    {
        $country = $this->currencyToCountry($currency);

        if (str_starts_with($title, "{$country} ") || str_starts_with($title, "{$currency} ")) {
            return $title;
        }

        return "{$country} {$title}";
    }

    private function normalizeProviderEventTitle(string $title, string $country): string
    {
        if (str_starts_with($title, "{$country} ")) {
            return $title;
        }

        return "{$country} {$title}";
    }

    private function calendarImportanceLabel(?int $importance): string
    {
        return match ($importance) {
            3 => 'High',
            2 => 'Medium',
            1 => 'Low',
            default => 'High',
        };
    }

    private function currencyToCountry(string $currency): string
    {
        return [
            'USD' => 'US',
            'GBP' => 'UK',
            'EUR' => 'Eurozone',
            'AUD' => 'Australia',
            'CAD' => 'Canada',
            'JPY' => 'Japan',
            'NZD' => 'New Zealand',
            'CHF' => 'Switzerland',
            'CNY' => 'China',
        ][$currency] ?? $currency;
    }

    private function countryToCurrency(string $country): string
    {
        return [
            'US' => 'USD',
            'UK' => 'GBP',
            'Eurozone' => 'EUR',
            'Australia' => 'AUD',
            'Canada' => 'CAD',
            'Japan' => 'JPY',
            'New Zealand' => 'NZD',
            'Switzerland' => 'CHF',
            'China' => 'CNY',
        ][$country] ?? strtoupper(substr($country, 0, 3));
    }

    private function tradingEconomicsCountryToLocal(string $country): string
    {
        return [
            'United States' => 'US',
            'United Kingdom' => 'UK',
            'Euro Area' => 'Eurozone',
            'European Union' => 'Eurozone',
        ][$country] ?? $country;
    }

    private function investingCountryToLocal(string $countryCell): string
    {
        $currency = strtoupper(trim(substr($countryCell, -3)));

        return $this->currencyToCountry($currency);
    }

    private function normalizeCountryFilter(string $country): string
    {
        $country = trim($country);

        return [
            'United States' => 'US',
            'United Kingdom' => 'UK',
            'Euro Area' => 'Eurozone',
            'European Union' => 'Eurozone',
        ][$country] ?? $country;
    }

    private function canonicalCalendarEventKey(string $event): string
    {
        $event = strtolower($event);
        $event = preg_replace('/^(us|uk|eurozone|australia|canada|japan|new zealand|united states|united kingdom|euro area)\s+/', '', $event);
        $event = preg_replace('/\b(m\/m|m-o-m|mom|month over month)\b/', 'mom', $event);
        $event = preg_replace('/\b(y\/y|y-o-y|yoy|year over year)\b/', 'yoy', $event);
        $event = preg_replace('/\b(q\/q|q-o-q|qoq|quarter over quarter)\b/', 'qoq', $event);
        $event = preg_replace('/\b(prelim|final|flash|revised|advance)\b/', '', $event);
        $event = preg_replace('/\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\b/', '', $event);
        $event = preg_replace('/\bq[1-4]\b/', '', $event);
        $event = preg_replace('/[^a-z0-9]+/', ' ', $event);
        $event = trim(preg_replace('/\s+/', ' ', $event));

        if (str_contains($event, 'ism non manufacturing pmi')) {
            return 'services pmi';
        }

        if (str_contains($event, 'jolts job openings')) {
            return 'job openings';
        }

        if (str_contains($event, 'nonfarm payrolls')) {
            return 'non farm payrolls';
        }

        if (str_contains($event, 'average hourly earnings')) {
            return 'average hourly earnings';
        }

        if (str_contains($event, 'unemployment rate')) {
            return 'unemployment rate';
        }

        $aliases = [
            'cash rate' => 'interest rate',
            'official cash rate' => 'interest rate',
            'overnight rate' => 'interest rate',
            'target overnight rate' => 'interest rate',
            'rba interest rate decision' => 'interest rate',
            'rba interest rate decision may' => 'interest rate',
            'interest rate decision' => 'interest rate',
            'interest rate decision may' => 'interest rate',
            'federal funds rate' => 'interest rate',
            'official bank rate' => 'interest rate',
            'main refinancing rate' => 'interest rate',
            'boj policy rate' => 'interest rate',
            'ism services pmi' => 'services pmi',
            'ism manufacturing pmi' => 'manufacturing pmi',
            'non farm employment change' => 'non farm payrolls',
            'nonfarm payrolls' => 'non farm payrolls',
            'adp nonfarm employment change' => 'adp non farm employment change',
            'jolts job openings' => 'job openings',
            'claimant count change' => 'claimant count change',
            'rbnz monetary policy statement' => 'monetary policy statement',
            'rbnz rate statement' => 'rate statement',
        ];

        return $aliases[$event] ?? $event;
    }

    private function parseCalendarNumber($value): ?float
    {
        if ($value === null) {
            return null;
        }

        $value = trim((string) $value);

        if ($value === '' || $value === '-' || $value === '|') {
            return null;
        }

        if (str_contains($value, '|')) {
            $value = explode('|', $value)[0];
        }

        $value = str_replace([',', '%', '<', '>'], '', $value);
        $multiplier = 1;
        $suffix = strtoupper(substr($value, -1));

        if (in_array($suffix, ['K', 'M', 'B', 'T'], true)) {
            $value = substr($value, 0, -1);
            $multiplier = match ($suffix) {
                'K' => 1000,
                'M' => 1000000,
                'B' => 1000000000,
                'T' => 1000000000000,
            };
        }

        if (!is_numeric($value)) {
            return null;
        }

        return round(((float) $value) * $multiplier, 6);
    }

    private function calculateCalendarImpact(string $event, ?float $actual, ?float $forecast, ?float $previous): string
    {
        $comparison = $forecast ?? $previous;

        if ($actual === null || $comparison === null) {
            return 'Neutral';
        }

        $higherIsBearish = preg_match('/unemployment|jobless|claimant|claims|inventories|deficit|costs|inflation expectations/i', $event) === 1;

        if (abs($actual - $comparison) < 0.000001) {
            return 'Neutral';
        }

        if ($higherIsBearish) {
            return $actual > $comparison ? 'Bearish' : 'Bullish';
        }

        return $actual > $comparison ? 'Bullish' : 'Bearish';
    }

    /**
     * Get series configuration
     */
    private function getSeriesConfig(string $seriesId): array
    {
        $configs = [
            'CPIAUCNS' => [
                'event' => 'US CPI',
                'time' => '08:30:00',
            ],
            'UNRATE' => [
                'event' => 'US Unemployment Rate',
                'time' => '08:30:00',
            ],
            'CPILFENS' => [
                'event' => 'US Core CPI',
                'time' => '08:30:00',
            ],
            'FEDFUNDS' => [
                'event' => 'Federal Funds Rate',
                'time' => '14:00:00',
            ],
            'RETAILMPCSMSA' => [
                'event' => 'US Retail Sales',
                'time' => '09:30:00',
            ],
            
        ];

        return $configs[$seriesId] ?? [
            'event' => $seriesId,
            'time' => '00:00:00',
        ];
    }

    /**
     * Get decimal places configuration for each series
     */
    private function getDecimalPlaces(string $seriesId): int
    {
        $decimalConfig = [
            // CPI and inflation: 1 decimal (e.g., 3.2%)
            'CPIAUCNS' => 1,
            'CPIAUCSL' => 1,
            'CPILFENS' => 1,
            'CPILFESL' => 1,
            'PCEPI' => 1,           // PCE Price Index
            'PCEPILFE' => 1,        // Core PCE

            // Interest rates: 2 decimals (e.g., 3.88%)
            'FEDFUNDS' => 2,
            'DFF' => 2,             // Effective Federal Funds Rate
            'DPRIME' => 2,          // Bank Prime Loan Rate
            'TB3MS' => 2,           // 3-Month Treasury Bill
            'GS10' => 2,            // 10-Year Treasury

            // Unemployment: 1 decimal (e.g., 3.7%)
            'UNRATE' => 1,
            'CIVPART' => 1,         // Civilian Participation Rate
            'EMRATIO' => 1,         // Employment-Population Ratio

            // GDP and retail sales: 1 decimal for percentages
            'GDPC1_PC1' => 1,       // Real GDP growth
            'RETAILMPCSMSA' => 1,

            // Default: 2 decimals
            'default' => 2,
        ];

        return $decimalConfig[$seriesId] ?? $decimalConfig['default'];
    }

    /**
     * Format numeric value with appropriate decimal places
     */
    private function formatNumericValue($value, string $seriesId): string
    {
        if ($value === '.' || $value === null || $value === '') {
            return '.';
        }

        if (!is_numeric($value)) {
            return (string)$value;
        }

        // Get decimal places for this series
        $decimalPlaces = $this->getDecimalPlaces($seriesId);

        $floatValue = (float)$value;

        $formatted = number_format($floatValue, $decimalPlaces, '.', '');

        if ($decimalPlaces > 0) {
            // Remove trailing zeros and decimal point if needed
            $formatted = preg_replace('/\.?0+$/', '', $formatted);
        }

        return $formatted;
    }

    /**
     * ✅ DIFFERENT IMPACT LOGIC FOR DIFFERENT INDICATORS
     */
    private function calculateImpact(string $seriesId, ?float $actual, ?float $previous): string
    {
        if ($actual === null || $previous === null) {
            return 'Neutral';
        }

        switch ($seriesId) {
            // actual higher than previous is bullish
            case 'CPIAUCNS':
            case 'CPIAUCSL':
            case 'CPILFENS':
            case 'CPILFESL':
            case 'FEDFUNDS':
            case 'RETAILMPCSMSA':
                if ($actual > $previous) {
                    return 'Bullish';
                } elseif ($actual < $previous) {
                    return 'Bearish';
                }
                break;

            // actual higher than previous is bearish
            case 'UNRATE':
                if ($actual > $previous) {
                    return 'Bearish';
                } elseif ($actual < $previous) {
                    return 'Bullish';
                }
                break;

            default:
                // Default: Higher = Bullish
                if ($actual > $previous) {
                    return 'Bullish';
                } elseif ($actual < $previous) {
                    return 'Bearish';
                }
        }

        return 'Neutral';
    }
}
