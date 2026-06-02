<?php

namespace App\Http\Service;

use App\Models\RetailSentiment;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use RuntimeException;

class RetailSentimentService
{
    public function getRetailSentiment(array $filters = []): array
    {
        $payload = $this->fetchSourceData((bool) ($filters['refresh'] ?? false));
        $this->persistDailySentimentSnapshot($payload);

        $groupBy = $this->normalizeGroupBy($filters['group_by'] ?? null);

        return $groupBy === RetailSentiment::GROUP_BY_BROKERS
            ? $this->buildBrokerResponse($payload, $filters)
            : $this->buildPairResponse($payload, $filters);
    }

    public function getFiltersMeta(): array
    {
        $payload = $this->fetchSourceData();
        $availableBrokers = [];

        foreach ($payload['broker_titles'] ?? [] as $code => $title) {
            if ($code === 'fxcm') {
                continue;
            }

            $availableBrokers[] = [
                'code' => $code,
                'name' => $title,
            ];
        }

        return [
            'supported_pairs' => RetailSentiment::supportedPairs(),
            'available_brokers' => array_values($availableBrokers),
            'default_group_by' => RetailSentiment::GROUP_BY_PAIRS,
            'default_pair' => RetailSentiment::DEFAULT_PAIR,
            'default_broker' => RetailSentiment::DEFAULT_BROKER,
            'source' => [
                'name' => 'FXSSI',
                'endpoint' => config('services.retail_sentiment.endpoint'),
            ],
        ];
    }

    private function buildPairResponse(array $payload, array $filters): array
    {
        $pair = RetailSentiment::normalizePair($filters['pair'] ?? null) ?? RetailSentiment::DEFAULT_PAIR;
        $pairData = $payload['pairs'][$pair] ?? null;

        if (!$pairData) {
            throw new RuntimeException("Retail sentiment is not available for pair {$pair}.");
        }

        $selectedBrokerCodes = $this->resolveRequestedBrokers($filters['brokers'] ?? null, $payload['broker_titles'] ?? []);
        $rows = [];

        foreach ($pairData as $brokerCode => $value) {
            if (in_array($brokerCode, ['average', 'oip'], true)) {
                continue;
            }

            if (!empty($selectedBrokerCodes) && !in_array($brokerCode, $selectedBrokerCodes, true)) {
                continue;
            }

            if ($brokerCode === 'fxcm') {
                continue;
            }

            $rows[] = $this->formatRow(
                $pair,
                $brokerCode,
                $payload['broker_titles'][$brokerCode] ?? RetailSentiment::DEFAULT_BROKER_TITLES[$brokerCode] ?? strtoupper($brokerCode),
                (float) $value,
                (int) ($payload['broker_weights'][$brokerCode] ?? 0)
            );
        }

        if (empty($rows)) {
            throw new RuntimeException("No retail sentiment rows matched for pair {$pair}.");
        }

        return [
            'group_by' => RetailSentiment::GROUP_BY_PAIRS,
            'selected_pair' => $pair,
            'selected_broker' => null,
            'items' => array_values($rows),
            'summary' => $this->buildSummary($rows, $pairData['average'] ?? null),
            'available_filters' => $this->getFiltersMeta(),
            'source' => $this->sourceMeta($payload),
        ];
    }

    private function buildBrokerResponse(array $payload, array $filters): array
    {
        $brokerCode = RetailSentiment::normalizeBroker($filters['broker'] ?? null, $payload['broker_titles'] ?? [])
            ?? RetailSentiment::DEFAULT_BROKER;

        $brokerData = $payload['brokers'][$brokerCode] ?? null;

        if (!$brokerData) {
            throw new RuntimeException("Retail sentiment is not available for broker {$brokerCode}.");
        }

        $requestedPairs = $this->resolveRequestedPairs($filters['pairs'] ?? null);
        $pairs = empty($requestedPairs) ? RetailSentiment::supportedPairs() : $requestedPairs;
        $rows = [];

        foreach ($pairs as $pair) {
            if (!array_key_exists($pair, $brokerData)) {
                continue;
            }

            $rows[] = $this->formatRow(
                $pair,
                $brokerCode,
                $payload['broker_titles'][$brokerCode] ?? RetailSentiment::DEFAULT_BROKER_TITLES[$brokerCode] ?? strtoupper($brokerCode),
                (float) $brokerData[$pair],
                (int) ($payload['pair_weights'][$pair] ?? 0)
            );
        }

        if (empty($rows)) {
            throw new RuntimeException("No retail sentiment rows matched for broker {$brokerCode}.");
        }

        return [
            'group_by' => RetailSentiment::GROUP_BY_BROKERS,
            'selected_pair' => null,
            'selected_broker' => [
                'code' => $brokerCode,
                'name' => $payload['broker_titles'][$brokerCode] ?? RetailSentiment::DEFAULT_BROKER_TITLES[$brokerCode] ?? strtoupper($brokerCode),
            ],
            'items' => array_values($rows),
            'summary' => $this->buildSummary($rows),
            'available_filters' => $this->getFiltersMeta(),
            'source' => $this->sourceMeta($payload),
        ];
    }   

    private function formatRow(string $pair, string $brokerCode, string $brokerName, float $buyers, int $weight): array
    {
        $buyers = round($buyers, 2);
        $sellers = round(100 - $buyers, 2);

        return [
            'pair' => $pair,
            'broker_code' => $brokerCode,
            'broker_name' => $brokerName,
            'buy_percentage' => $buyers,
            'sell_percentage' => $sellers,
            'weight' => $weight,
            'signal' => $buyers >= 50 ? 'sell_bias' : 'buy_bias',
        ];
    }

    private function buildSummary(array $rows, mixed $providedAverage = null): array
    {
        $buyAverage = $providedAverage !== null
            ? round((float) $providedAverage, 2)
            : round(array_sum(array_column($rows, 'buy_percentage')) / count($rows), 2);

        return [
            'average_buy_percentage' => $buyAverage,
            'average_sell_percentage' => round(100 - $buyAverage, 2),
            'total_rows' => count($rows),
        ];
    }

    private function resolveRequestedPairs(mixed $pairs): array
    {
        $pairs = is_array($pairs) ? $pairs : explode(',', (string) $pairs);
        $normalized = [];

        foreach ($pairs as $pair) {
            $normalizedPair = RetailSentiment::normalizePair($pair);

            if ($normalizedPair) {
                $normalized[] = $normalizedPair;
            }
        }

        return array_values(array_unique($normalized));
    }

    private function resolveRequestedBrokers(mixed $brokers, array $brokerTitles): array
    {
        $brokers = is_array($brokers) ? $brokers : explode(',', (string) $brokers);
        $normalized = [];

        foreach ($brokers as $broker) {
            $normalizedBroker = RetailSentiment::normalizeBroker($broker, $brokerTitles);

            if ($normalizedBroker && $normalizedBroker !== 'fxcm') {
                $normalized[] = $normalizedBroker;
            }
        }

        return array_values(array_unique($normalized));
    }

    private function normalizeGroupBy(?string $groupBy): string
    {
        return $groupBy === RetailSentiment::GROUP_BY_BROKERS
            ? RetailSentiment::GROUP_BY_BROKERS
            : RetailSentiment::GROUP_BY_PAIRS;
    }

    private function fetchSourceData(bool $forceRefresh = false): array
    {
        $cacheKey = 'retail_sentiment.current_ratios';

        if ($forceRefresh) {
            Cache::forget($cacheKey);
        }

        return Cache::remember(
            $cacheKey,
            now()->addSeconds((int) config('services.retail_sentiment.cache_seconds', 300)),
            fn() => $this->requestSourceData()
        );
    }

    private function requestSourceData(): array
    {
        $response = Http::acceptJson()
            ->timeout((int) config('services.retail_sentiment.timeout', 20))
            ->get(config('services.retail_sentiment.endpoint'));

        if ($response->failed()) {
            throw new RuntimeException('Unable to fetch live retail sentiment data from the upstream provider.');
        }

        $payload = $response->json();

        if (!is_array($payload) || !isset($payload['pairs'], $payload['brokers'], $payload['broker_titles'])) {
            throw new RuntimeException('Retail sentiment provider returned an unexpected response format.');
        }

        return $payload;
    }

    private function persistDailySentimentSnapshot(array $payload): void
    {
        $pairs = $payload['pairs'] ?? [];
        $brokerTitles = $payload['broker_titles'] ?? [];
        $snapshotDate = now()->startOfDay();
        $now = now();
        $rows = [];

        foreach (RetailSentiment::supportedPairs() as $pair) {
            $assetId = $this->assetId($pair);
            $pairData = $pairs[$pair] ?? null;

            if (!$assetId || !is_array($pairData)) {
                continue;
            }

            foreach ($pairData as $brokerCode => $buyPercentage) {
                if (in_array($brokerCode, ['average', 'oip', 'fxcm'], true) || !is_numeric($buyPercentage)) {
                    continue;
                }

                if (!array_key_exists($brokerCode, $brokerTitles) && !array_key_exists($brokerCode, RetailSentiment::DEFAULT_BROKER_TITLES)) {
                    continue;
                }

                $bullishPercentage = round((float) $buyPercentage, 2);

                $rows[] = [
                    'asset_id' => $assetId,
                    'bullish_percentage' => $bullishPercentage,
                    'bearish_percentage' => round(100 - $bullishPercentage, 2),
                    'broker_source' => $brokerCode,
                    'timestamp' => $snapshotDate,
                    'created_at' => $now,
                    'updated_at' => $now,
                ];
            }
        }

        if (empty($rows)) {
            return;
        }

        DB::table('sentimental_retail_sentiment')->upsert(
            $rows,
            ['asset_id', 'broker_source', 'timestamp'],
            ['bullish_percentage', 'bearish_percentage', 'updated_at']
        );
    }

    private function assetId(string $pair): ?int
    {
        $normalizedPair = RetailSentiment::normalizePair($pair);

        if (!$normalizedPair) {
            return null;
        }

        $assetId = DB::table('assets')
            ->where('asset_symbol', $normalizedPair)
            ->value('asset_id');

        return $assetId ? (int) $assetId : null;
    }

    private function sourceMeta(array $payload): array
    {
        return [
            'provider' => 'FXSSI',
            'endpoint' => config('services.retail_sentiment.endpoint'),
            'server_time_text' => $payload['server_time_text'] ?? null,
            'formed_unix' => $payload['formed'] ?? null,
            'cache_seconds' => (int) config('services.retail_sentiment.cache_seconds', 300),
        ];
    }
}
