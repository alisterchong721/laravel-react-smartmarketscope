<?php

return [

    /*
    |--------------------------------------------------------------------------
    | Third Party Services
    |--------------------------------------------------------------------------
    |
    | This file is for storing the credentials for third party services such
    | as Mailgun, Postmark, AWS and more. This file provides the de facto
    | location for this type of information, allowing packages to have
    | a conventional file to locate the various service credentials.
    |
    */

    'postmark' => [
        'key' => env('POSTMARK_API_KEY'),
    ],

    'resend' => [
        'key' => env('RESEND_API_KEY'),
    ],

    'ses' => [
        'key' => env('AWS_ACCESS_KEY_ID'),
        'secret' => env('AWS_SECRET_ACCESS_KEY'),
        'region' => env('AWS_DEFAULT_REGION', 'us-east-1'),
    ],

    'slack' => [
        'notifications' => [
            'bot_user_oauth_token' => env('SLACK_BOT_USER_OAUTH_TOKEN'),
            'channel' => env('SLACK_BOT_USER_DEFAULT_CHANNEL'),
        ],
    ],

    'retail_sentiment' => [
        'endpoint' => env('RETAIL_SENTIMENT_ENDPOINT', 'https://fxssi.com/api/current-ratios'),
        'timeout' => env('RETAIL_SENTIMENT_TIMEOUT', 20),
        'cache_seconds' => env('RETAIL_SENTIMENT_CACHE_SECONDS', 300),
    ],

    'cot_report' => [
        'endpoint' => env('COT_REPORT_ENDPOINT', 'https://publicreporting.cftc.gov/resource/6dca-aqww.json'),
        'timeout' => env('COT_REPORT_TIMEOUT', 20),
        'page_size' => env('COT_REPORT_PAGE_SIZE', 1000),
        'upsert_batch_size' => env('COT_REPORT_UPSERT_BATCH_SIZE', 100),
    ],

    'marketaux' => [
        'api_key' => env('MARKETAUX_API_KEY'),
        'endpoint' => env('MARKETAUX_ENDPOINT', 'https://api.marketaux.com/v1/news/all'),
        'timeout' => env('MARKETAUX_TIMEOUT', 20),
        'language' => env('MARKETAUX_LANGUAGE', 'en'),
        'limit' => env('MARKETAUX_LIMIT', 25),
    ],

    'openai' => [
        'api_key' => env('OPENAI_API_KEY'),
        'endpoint' => env('OPENAI_RESPONSES_ENDPOINT', 'https://api.openai.com/v1/responses'),
        'model' => env('OPENAI_MODEL', 'gpt-5-nano'),
        'chatbot_model' => env('OPENAI_CHATBOT_MODEL', env('OPENAI_MODEL', 'gpt-5-nano')),
        'timeout' => env('OPENAI_TIMEOUT', 45),
    ],

    'news_sentiment' => [
        'cache_seconds' => env('NEWS_SENTIMENT_CACHE_SECONDS', 900),
        'lookback_hours' => env('NEWS_SENTIMENT_LOOKBACK_HOURS', 24),
        'analysis_batch_size' => env('NEWS_SENTIMENT_ANALYSIS_BATCH_SIZE', 25),
    ],

    'forex_factory' => [
        'endpoint_base' => env('FOREX_FACTORY_ENDPOINT_BASE', 'https://nfs.faireconomy.media'),
        'timeout' => env('FOREX_FACTORY_TIMEOUT', 20),
        'timezone' => env('FOREX_FACTORY_TIMEZONE', 'Asia/Kuala_Lumpur'),
        'sync_cooldown_seconds' => env('FOREX_FACTORY_SYNC_COOLDOWN_SECONDS', 900),
        'impacts' => array_filter(array_map(
            'trim',
            explode(',', env('FOREX_FACTORY_IMPACTS', 'High'))
        )),
        'currencies' => array_filter(array_map(
            'trim',
            explode(',', env('FOREX_FACTORY_CURRENCIES', 'USD,GBP,EUR,AUD,CAD,JPY'))
        )),
        'periods' => array_filter(array_map(
            'trim',
            explode(',', env('FOREX_FACTORY_PERIODS', 'thisweek,nextweek'))
        )),
    ],

    'seasonality' => [
        'endpoint' => env('SEASONALITY_ENDPOINT', 'https://api.frankfurter.app'),
        'timeout' => env('SEASONALITY_TIMEOUT', 20),
    ],

    'trading_economics' => [
        'endpoint_base' => env('TRADING_ECONOMICS_ENDPOINT_BASE', 'https://api.tradingeconomics.com'),
        'api_key' => env('TRADING_ECONOMICS_API_KEY'),
        'timeout' => env('TRADING_ECONOMICS_TIMEOUT', 20),
        'countries' => array_filter(array_map(
            'trim',
            explode(',', env('TRADING_ECONOMICS_COUNTRIES', 'Australia,United States,United Kingdom,Euro Area,Canada,Japan'))
        )),
    ],

    'investing_calendar' => [
        'endpoint' => env('INVESTING_CALENDAR_ENDPOINT', 'https://www.investing.com/economic-calendar/Service/getCalendarFilteredData'),
        'timeout' => env('INVESTING_CALENDAR_TIMEOUT', 20),
        'timezone' => env('INVESTING_CALENDAR_TIMEZONE', 8),
        'event_pages' => [
            'US' => [
                'interest rate' => 'https://www.investing.com/economic-calendar/interest-rate-decision-168',
                'cpi yoy' => 'https://www.investing.com/economic-calendar/cpi-733',
                'cpi mom' => 'https://www.investing.com/economic-calendar/cpi-733',
                'core cpi mom' => 'https://www.investing.com/economic-calendar/core-cpi-56',
                'core cpi yoy' => 'https://www.investing.com/economic-calendar/core-cpi-736',
                'non farm payrolls' => 'https://www.investing.com/economic-calendar/nonfarm-payrolls-227',
                'unemployment rate' => 'https://www.investing.com/economic-calendar/unemployment-rate-300',
                'average hourly earnings' => 'https://www.investing.com/economic-calendar/average-hourly-earnings-8',
                'job openings' => 'https://www.investing.com/economic-calendar/jolts-job-openings-1057',
                'retail sales mom' => 'https://www.investing.com/economic-calendar/retail-sales-256',
                'ism manufacturing pmi' => 'https://www.investing.com/economic-calendar/ism-manufacturing-pmi-173',
                'ism services pmi' => 'https://www.investing.com/economic-calendar/ism-non-manufacturing-pmi-176',
                'gdp qoq' => 'https://www.investing.com/economic-calendar/gdp-375',
            ],
            'UK' => [
                'interest rate' => 'https://www.investing.com/economic-calendar/interest-rate-decision-170',
                'cpi yoy' => 'https://www.investing.com/economic-calendar/cpi-67',
                'gdp mom' => 'https://www.investing.com/economic-calendar/gdp-121',
                'claimant count change' => 'https://www.investing.com/economic-calendar/claimant-count-change-7',
                'unemployment rate' => 'https://www.investing.com/economic-calendar/unemployment-rate-297',
                'average earnings' => 'https://www.investing.com/economic-calendar/average-earnings-index-bonus-25',
                'retail sales mom' => 'https://www.investing.com/economic-calendar/retail-sales-27',
                'manufacturing pmi' => 'https://www.investing.com/economic-calendar/manufacturing-pmi-204',
                'services pmi' => 'https://www.investing.com/economic-calendar/services-pmi-274',
            ],
            'Eurozone' => [
                'interest rate' => 'https://www.investing.com/economic-calendar/interest-rate-decision-164',
                'cpi yoy' => 'https://www.investing.com/economic-calendar/cpi-68',
                'core cpi yoy' => 'https://www.investing.com/economic-calendar/core-cpi-317',
                'gdp qoq' => 'https://www.investing.com/economic-calendar/gdp-105',
                'unemployment rate' => 'https://www.investing.com/economic-calendar/unemployment-rate-296',
                'retail sales mom' => 'https://www.investing.com/economic-calendar/retail-sales-254',
                'manufacturing pmi' => 'https://www.investing.com/economic-calendar/manufacturing-pmi-201',
                'services pmi' => 'https://www.investing.com/economic-calendar/services-pmi-272',
            ],
            'Australia' => [
                'interest rate' => 'https://www.investing.com/economic-calendar/interest-rate-decision-171',
                'employment change' => 'https://www.investing.com/economic-calendar/employment-change-94',
                'unemployment rate' => 'https://www.investing.com/economic-calendar/unemployment-rate-302',
                'cpi qoq' => 'https://www.investing.com/economic-calendar/cpi-48',
                'trimmed mean cpi qoq' => 'https://www.investing.com/economic-calendar/trimmed-mean-cpi-120',
                'wage price index' => 'https://www.investing.com/economic-calendar/wage-price-index-102',
                'retail sales mom' => 'https://www.investing.com/economic-calendar/retail-sales-262',
                'gdp qoq' => 'https://www.investing.com/economic-calendar/gdp-101',
            ],
            'Canada' => [
                'interest rate' => 'https://www.investing.com/economic-calendar/interest-rate-decision-166',
                'employment change' => 'https://www.investing.com/economic-calendar/employment-change-95',
                'unemployment rate' => 'https://www.investing.com/economic-calendar/unemployment-rate-301',
                'cpi mom' => 'https://www.investing.com/economic-calendar/cpi-69',
                'median cpi yoy' => 'https://www.investing.com/economic-calendar/median-cpi-1714',
                'trimmed cpi yoy' => 'https://www.investing.com/economic-calendar/trimmed-cpi-1715',
                'retail sales mom' => 'https://www.investing.com/economic-calendar/retail-sales-258',
                'core retail sales mom' => 'https://www.investing.com/economic-calendar/core-retail-sales-59',
                'gdp mom' => 'https://www.investing.com/economic-calendar/gdp-125',
                'manufacturing pmi' => 'https://www.investing.com/economic-calendar/ivey-pmi-183',
            ],
            'Japan' => [
                'interest rate' => 'https://www.investing.com/economic-calendar/interest-rate-decision-165',
                'national core cpi yoy' => 'https://www.investing.com/economic-calendar/national-core-cpi-344',
                'tokyo core cpi yoy' => 'https://www.investing.com/economic-calendar/tokyo-core-cpi-328',
                'gdp qoq' => 'https://www.investing.com/economic-calendar/gdp-104',
                'retail sales yoy' => 'https://www.investing.com/economic-calendar/retail-sales-236',
                'unemployment rate' => 'https://www.investing.com/economic-calendar/unemployment-rate-299',
            ],
        ],
        'importances' => array_map(
            'intval',
            array_filter(array_map('trim', explode(',', env('INVESTING_CALENDAR_IMPORTANCES', '1,2,3'))))
        ),
    ],

];
