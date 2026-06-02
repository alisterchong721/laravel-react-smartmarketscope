<?php

namespace App\Http\Service;

use App\Models\FundamentalData;

class FundamentalDataService
{
    private const LIVE_SOURCE = 'Forex Factory';

    private const HIGH_IMPACT_EVENT_KEYS = [
        'interest_rate',
        'cpi',
        'core_cpi',
        'trimmed_mean_cpi',
        'unemployment_rate',
        'employment_change',
        'average_hourly_earnings',
        'non_farm_payrolls',
        'jolts',
        'gdp',
        'retail_sales',
        'core_retail_sales',
        'manufacturing_pmi',
        'services_pmi',
        'wage_price_index',
        'average_earnings',
        'claimant_count_change',
        'median_cpi',
        'trimmed_cpi',
        'tokyo_core_cpi',
        'national_core_cpi',
        'boj_outlook_report',
    ];

    private const COUNTRY_HIGH_IMPACT_EVENTS = [
        'US' => [
            'interest_rate',
            'cpi',
            'core_cpi',
            'non_farm_payrolls',
            'unemployment_rate',
            'average_hourly_earnings',
            'jolts',
            'retail_sales',
            'manufacturing_pmi',
            'services_pmi',
            'gdp',
        ],
        'UK' => [
            'interest_rate',
            'cpi',
            'gdp',
            'claimant_count_change',
            'unemployment_rate',
            'average_earnings',
            'retail_sales',
            'manufacturing_pmi',
            'services_pmi',
        ],
        'Eurozone' => [
            'interest_rate',
            'cpi',
            'core_cpi',
            'gdp',
            'unemployment_rate',
            'retail_sales',
            'manufacturing_pmi',
            'services_pmi',
        ],
        'Australia' => [
            'interest_rate',
            'employment_change',
            'unemployment_rate',
            'cpi',
            'trimmed_mean_cpi',
            'wage_price_index',
            'retail_sales',
            'gdp',
        ],
        'Canada' => [
            'interest_rate',
            'employment_change',
            'unemployment_rate',
            'cpi',
            'median_cpi',
            'trimmed_cpi',
            'retail_sales',
            'core_retail_sales',
            'gdp',
            'manufacturing_pmi',
        ],
        'Japan' => [
            'interest_rate',
            'national_core_cpi',
            'tokyo_core_cpi',
            'gdp',
            'retail_sales',
            'unemployment_rate',
        ],
    ];

    // ============================================
    // EXISTING METHODS (keep as is)
    // ============================================

    public function getCountryLatestEvent(string $country): ?array
    {
        $rows = FundamentalData::where('country', $country)
            ->where(function ($query) {
                $query->whereNotNull('actual')
                    ->orWhereNotNull('actual_raw')
                    ->orWhereNotNull('forecast')
                    ->orWhereNotNull('forecast_raw')
                    ->orWhereNotNull('previous')
                    ->orWhereNotNull('previous_raw');
            })
            ->where(function ($query) {
                $query->where(function ($query) {
                    $query->where('source', self::LIVE_SOURCE)
                        ->where('importance', 'High');
                })->orWhere('source', '!=', self::LIVE_SOURCE);
            })
            ->orderBy('date', 'desc')
            ->orderBy('time', 'desc')
            ->orderByRaw('CASE WHEN source = ? THEN 0 ELSE 1 END', [self::LIVE_SOURCE])
            ->get([
                'country',
                'event',
                'actual',
                'actual_raw',
                'actual_source',
                'actual_synced_at',
                'forecast',
                'forecast_raw',
                'previous',
                'previous_raw',
                'date',
                'impact',
                'importance',
                'source',
            ]);

        $latestEventsByKey = [];

        foreach ($rows as $latestData) {
            $eventKey = $this->canonicalEventKey($latestData->event);

            if (!in_array($eventKey, self::HIGH_IMPACT_EVENT_KEYS, true)) {
                continue;
            }

            if (!$this->isAggregateCountryEvent($latestData->country, $latestData->event)) {
                continue;
            }

            if (isset($latestEventsByKey[$eventKey])
                && $this->preferredCountryEventRow($latestEventsByKey[$eventKey]['_row'], $latestData) !== $latestData
            ) {
                continue;
            }

            $impactColor = $this->impactColor($latestData->impact);
            $impactClass = $this->impactColorClass($latestData->impact);
            $latestEventsByKey[$eventKey] = [
                '_row' => $latestData,
                'country' => $latestData->country,
                'event' => $this->preferredForexFactoryEventName($latestData->country, $eventKey, $latestData->event),
                'actual' => $latestData->actual_raw ?? $this->formatNullableNumber($latestData->actual),
                'actual_color' => $impactColor,
                'actualColor' => $impactColor,
                'actual_class' => $impactClass,
                'actualClass' => $impactClass,
                'forecast' => $latestData->forecast_raw ?? $this->formatNullableNumber($latestData->forecast),
                'previous' => $latestData->previous_raw ?? $this->formatNullableNumber($latestData->previous),
                'formatted_date' => $latestData->date->format('d/m/Y'),
                'impact' => $latestData->impact,
                'impact_color' => $impactColor,
                'impactColor' => $impactColor,
                'impact_class' => $impactClass,
                'impactClass' => $impactClass,
                'importance' => $latestData->importance ?? 'Historical',
                'source' => $latestData->source,
                'actual_source' => $latestData->actual_source,
                'actual_synced_at' => $latestData->actual_synced_at?->toIso8601String(),
                'is_live_source' => $latestData->source === self::LIVE_SOURCE,
            ];
        }

        $eventTemplate = self::COUNTRY_HIGH_IMPACT_EVENTS[$country] ?? array_keys($latestEventsByKey);
        $latestEventsData = [];

        foreach ($eventTemplate as $eventKey) {
            if (isset($latestEventsByKey[$eventKey])) {
                $eventData = $latestEventsByKey[$eventKey];
                unset($eventData['_row']);
                $latestEventsData[] = $eventData;
                continue;
            }

            $latestEventsData[] = [
                'country' => $country,
                'event' => $this->preferredForexFactoryEventName($country, $eventKey),
                'actual' => null,
                'actual_color' => 'default',
                'actualColor' => 'default',
                'actual_class' => '',
                'actualClass' => '',
                'forecast' => null,
                'previous' => null,
                'formatted_date' => null,
                'impact' => 'Neutral',
                'impact_color' => 'default',
                'impactColor' => 'default',
                'impact_class' => '',
                'impactClass' => '',
                'importance' => 'High',
                'source' => 'Awaiting Forex Factory',
                'actual_source' => null,
                'actual_synced_at' => null,
                'is_live_source' => false,
                'is_pending_source' => true,
            ];
        }

        return [
            'success' => true,
            'message' => 'Latest Data According Country Retrieved Successfully',
            'data' => $latestEventsData
        ];
    }

    private function preferredCountryEventRow(FundamentalData $current, FundamentalData $candidate): FundamentalData
    {
        $currentHasActual = $current->actual !== null || $current->actual_raw !== null;
        $candidateHasActual = $candidate->actual !== null || $candidate->actual_raw !== null;

        if ($candidateHasActual !== $currentHasActual) {
            return $candidateHasActual ? $candidate : $current;
        }

        $currentDate = $current->date?->timestamp ?? 0;
        $candidateDate = $candidate->date?->timestamp ?? 0;

        if ($candidateDate !== $currentDate) {
            return $candidateDate > $currentDate ? $candidate : $current;
        }

        $currentTime = (string) ($current->time ?? '');
        $candidateTime = (string) ($candidate->time ?? '');

        if ($candidateTime !== $currentTime) {
            return $candidateTime > $currentTime ? $candidate : $current;
        }

        $currentSourcePriority = $this->countryEventSourcePriority($current->source);
        $candidateSourcePriority = $this->countryEventSourcePriority($candidate->source);

        if ($candidateSourcePriority !== $currentSourcePriority) {
            return $candidateSourcePriority > $currentSourcePriority ? $candidate : $current;
        }

        if ($candidate->source === self::LIVE_SOURCE && $current->source !== self::LIVE_SOURCE) {
            return $candidate;
        }

        return $current;
    }

    private function countryEventSourcePriority(?string $source): int
    {
        return match ($source) {
            'Investing.com' => 3,
            self::LIVE_SOURCE => 2,
            default => 1,
        };
    }

    private function isAggregateCountryEvent(string $country, string $event): bool
    {
        if ($country !== 'Eurozone') {
            return true;
        }

        $event = strtolower($event);

        $memberCountryPrefixes = [
            'austrian',
            'belgian',
            'croatian',
            'cypriot',
            'dutch',
            'estonian',
            'finnish',
            'french',
            'german',
            'greek',
            'irish',
            'italian',
            'latvian',
            'lithuanian',
            'luxembourg',
            'maltese',
            'portuguese',
            'slovak',
            'slovenian',
            'spanish',
        ];

        foreach ($memberCountryPrefixes as $prefix) {
            if (str_contains($event, $prefix . ' ')) {
                return false;
            }
        }

        return true;
    }

    public function getEventCountryLatestData(?string $event, ?string $country, ?string $startDate = null, ?string $endDate = null): array
    {
        $query = FundamentalData::query()
            ->where('source', self::LIVE_SOURCE)
            ->orderByDesc('date')
            ->orderByDesc('time');

        if ($event) {
            $query->where('event', 'like', '%' . $event . '%');
        }

        if ($country) {
            $query->where('country', $country);
        }

        if ($startDate) {
            $query->whereDate('date', '>=', $startDate);
        }

        if ($endDate) {
            $query->whereDate('date', '<=', $endDate);
        }

        return $query->limit(250)->get()->map(function (FundamentalData $row) {
            $impactColor = $this->impactColor($row->impact);
            $impactClass = $this->impactColorClass($row->impact);

            return [
                'country' => $row->country,
                'currency' => $row->currency,
                'event' => $row->event,
                'actual' => $row->actual_raw ?? $this->formatNullableNumber($row->actual),
                'actual_color' => $impactColor,
                'actualColor' => $impactColor,
                'actual_class' => $impactClass,
                'actualClass' => $impactClass,
                'forecast' => $row->forecast_raw ?? $this->formatNullableNumber($row->forecast),
                'previous' => $row->previous_raw ?? $this->formatNullableNumber($row->previous),
                'formatted_date' => $row->date?->format('d/m/Y'),
                'date' => $row->date?->toDateString(),
                'time' => $row->time,
                'impact' => $row->impact,
                'impact_color' => $impactColor,
                'impactColor' => $impactColor,
                'impact_class' => $impactClass,
                'impactClass' => $impactClass,
                'importance' => $row->importance,
                'source' => $row->source,
                'actual_source' => $row->actual_source,
                'actual_synced_at' => $row->actual_synced_at?->toIso8601String(),
            ];
        })->all();
    }

    private function formatNullableNumber($value): ?string
    {
        if ($value === null) {
            return null;
        }

        return rtrim(rtrim(number_format((float) $value, 2, '.', ''), '0'), '.');
    }

    private function impactColor(?string $impact): string
    {
        return match ($impact) {
            'Bullish' => 'green',
            'Bearish' => 'red',
            default => 'default',
        };
    }

    private function impactColorClass(?string $impact): string
    {
        return match ($impact) {
            'Bullish' => 'text-green-600',
            'Bearish' => 'text-red-600',
            default => '',
        };
    }

    private function canonicalEventKey(string $event): string
    {
        $normalized = strtolower($event);
        $normalized = preg_replace('/^(us|uk|australia|canada|japan|eurozone|new zealand)\s+/', '', $normalized);

        return match (true) {
            str_contains($normalized, 'cash rate'),
            str_contains($normalized, 'federal funds rate'),
            str_contains($normalized, 'official bank rate'),
            str_contains($normalized, 'overnight rate'),
            str_contains($normalized, 'main refinancing rate'),
            str_contains($normalized, 'boj policy rate'),
            str_contains($normalized, 'interest rate'),
            str_contains($normalized, 'rate decision') => 'interest_rate',

            str_contains($normalized, 'trimmed mean cpi') => 'trimmed_mean_cpi',
            str_contains($normalized, 'trimmed cpi') => 'trimmed_cpi',
            str_contains($normalized, 'median cpi') => 'median_cpi',
            str_contains($normalized, 'tokyo core cpi') => 'tokyo_core_cpi',
            str_contains($normalized, 'national core cpi') => 'national_core_cpi',
            str_contains($normalized, 'boj outlook') => 'boj_outlook_report',
            str_contains($normalized, 'unemployment') => 'unemployment_rate',
            str_contains($normalized, 'average hourly earnings') => 'average_hourly_earnings',
            str_contains($normalized, 'average earnings') => 'average_earnings',
            str_contains($normalized, 'claimant count') => 'claimant_count_change',
            str_contains($normalized, 'wage price') => 'wage_price_index',
            str_contains($normalized, 'jolts') => 'jolts',
            str_contains($normalized, 'non-farm') => 'non_farm_payrolls',
            str_contains($normalized, 'gdp') => 'gdp',
            str_contains($normalized, 'core retail sales') => 'core_retail_sales',
            str_contains($normalized, 'retail sales') => 'retail_sales',
            str_contains($normalized, 'core cpi') => 'core_cpi',
            str_contains($normalized, 'cpi') => 'cpi',
            str_contains($normalized, 'services pmi') => 'services_pmi',
            str_contains($normalized, 'manufacturing pmi') => 'manufacturing_pmi',
            str_contains($normalized, 'ivey pmi') => 'manufacturing_pmi',
            str_contains($normalized, 'employment change') => 'employment_change',

            default => preg_replace('/[^a-z0-9]+/', '_', trim($normalized)),
        };
    }

    private function preferredForexFactoryEventName(string $country, string $eventKeyOrEvent, ?string $fallbackEvent = null): string
    {
        $eventKey = in_array($eventKeyOrEvent, self::HIGH_IMPACT_EVENT_KEYS, true)
            ? $eventKeyOrEvent
            : $this->canonicalEventKey($eventKeyOrEvent);

        $names = [
            'Australia' => [
                'interest_rate' => 'Australia Cash Rate',
                'unemployment_rate' => 'Australia Unemployment Rate',
                'cpi' => 'Australia CPI q/q',
                'trimmed_mean_cpi' => 'Australia Trimmed Mean CPI q/q',
                'retail_sales' => 'Australia Retail Sales m/m',
                'employment_change' => 'Australia Employment Change',
                'wage_price_index' => 'Australia Wage Price Index q/q',
                'gdp' => 'Australia GDP q/q',
            ],
            'Canada' => [
                'interest_rate' => 'Canada Overnight Rate',
                'employment_change' => 'Canada Employment Change',
                'unemployment_rate' => 'Canada Unemployment Rate',
                'cpi' => 'Canada CPI m/m',
                'median_cpi' => 'Canada Median CPI y/y',
                'trimmed_cpi' => 'Canada Trimmed CPI y/y',
                'core_retail_sales' => 'Canada Core Retail Sales m/m',
                'retail_sales' => 'Canada Retail Sales m/m',
                'gdp' => 'Canada GDP m/m',
                'manufacturing_pmi' => 'Canada Ivey PMI',
            ],
            'Eurozone' => [
                'interest_rate' => 'Eurozone Main Refinancing Rate',
                'cpi' => 'Eurozone CPI Flash Estimate y/y',
                'core_cpi' => 'Eurozone Core CPI Flash Estimate y/y',
                'gdp' => 'Eurozone Flash GDP q/q',
                'retail_sales' => 'Eurozone Retail Sales m/m',
                'unemployment_rate' => 'Eurozone Unemployment Rate',
                'manufacturing_pmi' => 'Eurozone Flash Manufacturing PMI',
                'services_pmi' => 'Eurozone Flash Services PMI',
            ],
            'Japan' => [
                'interest_rate' => 'Japan BOJ Policy Rate',
                'boj_outlook_report' => 'Japan BOJ Outlook Report',
                'tokyo_core_cpi' => 'Japan Tokyo Core CPI y/y',
                'national_core_cpi' => 'Japan National Core CPI y/y',
                'core_cpi' => $fallbackEvent && str_contains(strtolower($fallbackEvent), 'tokyo')
                    ? 'Japan Tokyo Core CPI y/y'
                    : 'Japan National Core CPI y/y',
                'cpi' => 'Japan CPI y/y',
                'gdp' => 'Japan Prelim GDP q/q',
                'retail_sales' => 'Japan Retail Sales y/y',
                'unemployment_rate' => 'Japan Unemployment Rate',
            ],
            'UK' => [
                'interest_rate' => 'UK Official Bank Rate',
                'cpi' => 'UK CPI y/y',
                'gdp' => 'UK GDP m/m',
                'claimant_count_change' => 'UK Claimant Count Change',
                'average_earnings' => 'UK Average Earnings Index 3m/y',
                'retail_sales' => 'UK Retail Sales m/m',
                'unemployment_rate' => 'UK Unemployment Rate',
                'manufacturing_pmi' => 'UK Flash Manufacturing PMI',
                'services_pmi' => 'UK Flash Services PMI',
            ],
            'US' => [
                'interest_rate' => 'US Federal Funds Rate',
                'cpi' => 'US CPI y/y',
                'core_cpi' => 'US Core CPI m/m',
                'retail_sales' => 'US Retail Sales m/m',
                'manufacturing_pmi' => 'US ISM Manufacturing PMI',
                'services_pmi' => 'US ISM Services PMI',
                'jolts' => 'US JOLTS Job Openings',
                'average_hourly_earnings' => 'US Average Hourly Earnings m/m',
                'non_farm_payrolls' => 'US Non-Farm Employment Change',
                'unemployment_rate' => 'US Unemployment Rate',
                'gdp' => 'US Advance GDP q/q',
            ],
        ];

        return $names[$country][$eventKey] ?? ($fallbackEvent ?? $eventKeyOrEvent);
    }

    // ============================================
    // CURRENCY IMPACT CALCULATION METHODS
    // ============================================

    private $impactScores = [
        'Bullish' => 1,
        'Bearish' => -1,
        'Neutral' => 0
    ];

    private $currencyPairs = [
        'EURUSD' => ['base' => 'EUR', 'quote' => 'USD'],
        'GBPUSD' => ['base' => 'GBP', 'quote' => 'USD'],
        'AUDUSD' => ['base' => 'AUD', 'quote' => 'USD'],
        'USDCAD' => ['base' => 'USD', 'quote' => 'CAD'],
        'USDJPY' => ['base' => 'USD', 'quote' => 'JPY'],
    ];

    private $currencyToCountry = [
        'USD' => 'US',
        'GBP' => 'UK',
        'EUR' => 'Eurozone',
        'AUD' => 'Australia',
        'CAD' => 'Canada',
        'JPY' => 'Japan'
    ];

    /**
     * Get only the latest unique events for a country
     * No duplicate event types
     */
    private function getLatestEvents(string $country): array
    {
        // Method 1: Reuse existing method
        $result = $this->getCountryLatestEvent($country);

        if ($result['success']) {
            // Transform to match expected format
            return array_map(function ($event) {
                return [
                    'event' => $event['event'],
                    'impact' => $event['impact'],
                    'date' => $event['formatted_date'],
                    'actual' => $event['actual'],
                    'forecast' => $event['forecast'],
                    'previous' => $event['previous']
                ];
            }, $result['data']);
        }

        return [];
    }

    private function calculateCountryScore(array $events): int
    {
        $totalScore = 0;

        foreach ($events as $event) {
            $score = $this->impactScores[$event['impact']] ?? 0;
            $totalScore += $score;
        }

        return $totalScore;
    }

    private function getImpactLabel(int $score): string
    {
        if ($score > 0) {
            return 'Bullish';
        } elseif ($score < 0) {
            return 'Bearish';
        } else {
            return 'Neutral';
        }
    }

    public function calculatePairImpact(string $pair): array
    {
        if (!isset($this->currencyPairs[$pair])) {
            return ['error' => 'Currency Pair not supported'];
        }

        // Get currencies from pair
        $baseCurrency = $this->currencyPairs[$pair]['base'];
        $quoteCurrency = $this->currencyPairs[$pair]['quote'];

        // Convert to country codes
        $baseCountry = $this->currencyToCountry[$baseCurrency] ?? $baseCurrency;
        $quoteCountry = $this->currencyToCountry[$quoteCurrency] ?? $quoteCurrency;

        // Get latest unique events for each country
        $baseEvents = $this->getLatestEvents($baseCountry);
        $quoteEvents = $this->getLatestEvents($quoteCountry);

        // Calculate scores
        $baseScore = $this->calculateCountryScore($baseEvents);
        $quoteScore = $this->calculateCountryScore($quoteEvents);

        // Final pair score: base currency strength minus quote currency strength.
        $pairScore = $baseScore - $quoteScore;

        // Determine impact
        $impact = $this->getImpactLabel($pairScore);

        return [
            'pair' => $pair,
            'base_currency' => $baseCurrency,
            'quote_currency' => $quoteCurrency,
            'base_country' => $baseCountry,
            'quote_country' => $quoteCountry,
            'base_score' => $baseScore,
            'quote_score' => $quoteScore,
            'pair_score' => $pairScore,
            'impact' => $impact,
            // 'events_considered' => [
            //     'base' => count($baseEvents),
            //     'quote' => count($quoteEvents)
            // ]
        ];
    }

    public function calculateAllPairs(): array
    {
        $results = [];

        foreach (array_keys($this->currencyPairs) as $pair) {
            $result = $this->calculatePairImpact($pair);
            if (!isset($result['error'])) {
                $results[] = $result;
            }
        }

        return $results;
    }
}
