<?php

namespace App\Models;

class RetailSentiment
{
    public const GROUP_BY_PAIRS = 'pairs';
    public const GROUP_BY_BROKERS = 'brokers';

    public const DEFAULT_PAIR = 'EURUSD';
    public const DEFAULT_BROKER = 'fxssi';

    public const SUPPORTED_PAIRS = [
        'EURUSD',
        'GBPUSD',
        'AUDUSD',
        'USDCAD',
        'USDJPY',
    ];

    public const DEFAULT_BROKER_TITLES = [
        'fxblue' => 'FXBlue',
        'dukscopy' => 'Dukascopy',
        'fiboforx' => 'FiboGroup',
        'ftroanda' => 'Oanda',
        'instfor' => 'Instaforex',
        'myfxbook' => 'MyFxBook',
        'fxssi' => 'FXSSI',
        'xm' => 'XMGroup',
        'amarkets' => 'Amarkets',
        'fxcm' => 'IG Group',
    ];

    public static function supportedPairs(): array
    {
        return self::SUPPORTED_PAIRS;
    }

    public static function normalizePair(?string $pair): ?string
    {
        if (!$pair) {
            return null;
        }

        $normalized = strtoupper(str_replace('/', '', trim($pair)));

        return in_array($normalized, self::SUPPORTED_PAIRS, true) ? $normalized : null;
    }

    public static function normalizeBroker(?string $broker, array $brokerTitles = []): ?string
    {
        if (!$broker) {
            return null;
        }

        $brokerTitles = array_replace(self::DEFAULT_BROKER_TITLES, $brokerTitles);
        $normalized = strtolower(trim($broker));

        if (array_key_exists($normalized, $brokerTitles)) {
            return $normalized;
        }

        foreach ($brokerTitles as $code => $title) {
            if (strtolower($title) === $normalized) {
                return $code;
            }
        }

        return null;
    }
}
