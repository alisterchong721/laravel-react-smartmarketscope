<?php

namespace App\Http\Service;

use App\Models\ChatMessage;
use App\Models\ChatSession;
use App\Models\CotReport;
use App\Models\RetailSentiment;
use App\Models\TradeRecord;
use App\Models\User;
use App\Support\TrackedMarketAsset;
use Carbon\CarbonInterface;
use Throwable;

class ChatbotContextService
{
    private const FUNDAMENTAL_PAIR_META = [
        'EURUSD' => ['base_country' => 'Eurozone', 'quote_country' => 'US'],
        'GBPUSD' => ['base_country' => 'UK', 'quote_country' => 'US'],
        'AUDUSD' => ['base_country' => 'Australia', 'quote_country' => 'US'],
        'USDCAD' => ['base_country' => 'US', 'quote_country' => 'Canada'],
        'USDJPY' => ['base_country' => 'US', 'quote_country' => 'Japan'],
    ];

    public function __construct(
        private OverviewDashboardService $overviewDashboardService,
        private CotReportService $cotReportService,
        private RetailSentimentService $retailSentimentService,
        private NewsSentimentService $newsSentimentService,
        private FundamentalDataService $fundamentalDataService,
    ) {
    }

    public function build(User $user, string $message, ChatSession $session): array
    {
        $assets = $this->detectAssets($message);
        $topics = $this->detectTopics($message);

        return [
            'generated_at' => $this->formatDateTime(now()),
            'presentation_guidelines' => [
                'audience' => 'Dashboard users, not developers.',
                'style' => 'Use friendly labels, short explanations, and local Malaysia time.',
                'avoid' => [
                    'raw database IDs such as trade_id or user_id',
                    'snake_case field names',
                    'ISO timestamps such as 2026-05-07T15:24:00+00:00',
                    'raw JSON or API-shaped data dumps',
                ],
            ],
            'question_analysis' => [
                'detected_assets' => $assets,
                'detected_topics' => $topics,
            ],
            'site_scope' => [
                'features' => [
                    'overview dashboard',
                    'fundamental analysis',
                    'COT sentiment',
                    'retail sentiment',
                    'news sentiment',
                    'trading journal',
                    'authentication and account pages',
                ],
                'supported_assets' => TrackedMarketAsset::promptReference(),
            ],
            'latest_site_data' => $this->buildSiteData($assets, $topics, $user),
            'recent_conversation' => $this->recentConversation($session),
        ];
    }

    private function buildSiteData(array $assets, array $topics, User $user): array
    {
        $assetFilter = empty($assets) ? null : implode(',', $assets);

        return [
            'overview_dashboard' => $this->safeCall(fn() => $this->overviewDashboardService->getOverview([
                'assets' => $assetFilter,
            ])),
            'fundamental_analysis' => $this->safeCall(fn() => $this->fundamentals($assets)),
            'cot_sentiment' => $this->shouldInclude($topics, ['cot', 'overview'])
                ? $this->safeCall(fn() => $this->cotReportService->getCotReport(['assets' => $assetFilter]))
                : ['included' => false, 'reason' => 'Question did not request COT details.'],
            'retail_sentiment' => $this->shouldInclude($topics, ['retail', 'overview'])
                ? $this->safeCall(fn() => $this->retail($assets))
                : ['included' => false, 'reason' => 'Question did not request retail sentiment details.'],
            'news_sentiment' => $this->shouldInclude($topics, ['news', 'overview'])
                ? $this->safeCall(fn() => $this->newsSentimentService->getNewsSentiment([
                    'assets' => $assetFilter,
                    'limit' => 8,
                ]))
                : ['included' => false, 'reason' => 'Question did not request news sentiment details.'],
            'trading_journal' => $this->shouldInclude($topics, ['trades', 'journal', 'overview'])
                ? $this->safeCall(fn() => $this->tradeSummary($user, $assets))
                : ['included' => false, 'reason' => 'Question did not request trading journal details.'],
        ];
    }

    private function fundamentals(array $assets): array
    {
        $assets = empty($assets) ? array_keys($this->supportedOverviewAssets()) : $assets;
        $supportedAssets = array_values(array_filter($assets, fn(string $asset) => $this->isSupportedFundamentalPair($asset)));

        return [
            'score_explanation' => [
                'country_event_impact_scores' => [
                    'Bullish' => 1,
                    'Bearish' => -1,
                    'Neutral' => 0,
                ],
                'pair_score_formula' => 'base_country_score - quote_country_score',
                'overview_score_formula' => '(pair_score / 10) * 100, clamped from -100 to +100',
                'example' => 'A pair_score of 2 appears as a dashboard fundamental score of +20. This is the same signal on the overview -100 to +100 bias scale, not a data mismatch.',
            ],
            'items' => array_map(
                fn(string $asset) => $this->fundamentalPairContext($asset),
                $supportedAssets
            ),
        ];
    }

    private function fundamentalPairContext(string $asset): array
    {
        $impact = $this->fundamentalDataService->calculatePairImpact($asset);
        $meta = self::FUNDAMENTAL_PAIR_META[$asset] ?? null;

        if (!$meta || isset($impact['error'])) {
            return $impact;
        }

        return [
            ...$impact,
            'base_country_latest_events' => $this->countryEvents($meta['base_country']),
            'quote_country_latest_events' => $this->countryEvents($meta['quote_country']),
            'explanation_hints' => [
                'base_score_meaning' => 'Positive base_score means the base currency has more bullish latest events; negative means more bearish latest events.',
                'quote_score_meaning' => 'Positive quote_score means the quote currency has more bullish latest events; this reduces the pair_score when the pair is base/quote.',
                'pair_impact_meaning' => 'Bullish means the base currency is fundamentally stronger than the quote currency based on the latest event impacts.',
            ],
        ];
    }

    private function countryEvents(string $country): array
    {
        $payload = $this->fundamentalDataService->getCountryLatestEvent($country);

        return [
            'country' => $country,
            'success' => (bool) ($payload['success'] ?? false),
            'events' => $payload['data'] ?? [],
        ];
    }

    private function retail(array $assets): array
    {
        $assets = empty($assets)
            ? RetailSentiment::supportedPairs()
            : array_values(array_intersect($assets, RetailSentiment::supportedPairs()));

        return [
            'items' => array_map(
                fn(string $asset) => $this->retailSentimentService->getRetailSentiment(['pair' => $asset]),
                $assets
            ),
        ];
    }

    private function tradeSummary(User $user, array $assets): array
    {
        $query = TradeRecord::query()
            ->where('user_id', $user->id)
            ->when(!empty($assets), fn($builder) => $builder->whereIn('asset_symbol', $assets))
            ->orderByDesc('entry_time');

        $trades = $query->limit(20)->get();
        $allUserTrades = TradeRecord::query()
            ->where('user_id', $user->id)
            ->when(!empty($assets), fn($builder) => $builder->whereIn('asset_symbol', $assets))
            ->get();

        $closedTrades = $allUserTrades->whereNotNull('exit_time');
        $winningTrades = $closedTrades->filter(fn(TradeRecord $trade) => (float) $trade->profit_loss > 0);
        $losingTrades = $closedTrades->filter(fn(TradeRecord $trade) => (float) $trade->profit_loss < 0);
        $totalProfitLoss = round((float) $allUserTrades->sum('profit_loss'), 2);

        return [
            'summary' => [
                'total_trades' => $allUserTrades->count(),
                'closed_trades' => $closedTrades->count(),
                'open_trades' => $allUserTrades->whereNull('exit_time')->count(),
                'winning_trades' => $winningTrades->count(),
                'losing_trades' => $losingTrades->count(),
                'net_profit_loss' => $this->formatMoney($totalProfitLoss),
                'win_rate' => $closedTrades->count() > 0
                    ? round(($winningTrades->count() / $closedTrades->count()) * 100, 1) . '%'
                    : '0%',
                'latest_entry_time' => $this->formatDateTime($trades->first()?->entry_time),
            ],
            'recent_trades' => $trades->map(fn(TradeRecord $trade) => [
                'trade' => trim(sprintf(
                    '%s %s',
                    strtoupper((string) $trade->asset_symbol),
                    strtoupper((string) $trade->direction)
                )),
                'entry' => [
                    'price' => $this->formatPrice($trade->entry_price),
                    'time' => $this->formatDateTime($trade->entry_time),
                ],
                'exit' => [
                    'price' => $this->formatPrice($trade->exit_price),
                    'time' => $this->formatDateTime($trade->exit_time),
                ],
                'profit_loss' => $this->formatMoney($trade->profit_loss),
                'result' => $this->tradeResult($trade->profit_loss),
                'duration' => $this->tradeDuration($trade),
                'notes' => $trade->notes ?: null,
            ])->values()->all(),
            'display_notes' => [
                'Use the trade label instead of internal trade IDs.',
                'All displayed times are Malaysia time (MYT, UTC+8).',
            ],
        ];
    }

    private function formatDateTime(mixed $dateTime): ?string
    {
        if (!$dateTime instanceof CarbonInterface) {
            return null;
        }

        return $dateTime
            ->copy()
            ->timezone('Asia/Kuala_Lumpur')
            ->format('d M Y, h:i A') . ' MYT';
    }

    private function formatMoney(mixed $value): ?string
    {
        if ($value === null || $value === '') {
            return null;
        }

        $amount = round((float) $value, 2);
        $sign = $amount > 0 ? '+' : ($amount < 0 ? '-' : '');

        return $sign . '$' . number_format(abs($amount), 2);
    }

    private function formatPrice(mixed $value): ?string
    {
        if ($value === null || $value === '') {
            return null;
        }

        return rtrim(rtrim(number_format((float) $value, 5, '.', ''), '0'), '.');
    }

    private function tradeResult(mixed $profitLoss): string
    {
        $value = (float) $profitLoss;

        return match (true) {
            $value > 0 => 'Win',
            $value < 0 => 'Loss',
            default => 'Flat',
        };
    }

    private function tradeDuration(TradeRecord $trade): ?string
    {
        if (!$trade->entry_time || !$trade->exit_time) {
            return null;
        }

        $minutes = $trade->entry_time->diffInMinutes($trade->exit_time, false);

        if ($minutes < 0) {
            return 'Exit time is before entry time; please check this journal entry.';
        }

        if ($minutes < 60) {
            return $minutes . ' minute' . ($minutes === 1 ? '' : 's');
        }

        $hours = round($minutes / 60, 1);

        return $hours . ' hour' . ($hours === 1.0 ? '' : 's');
    }

    private function recentConversation(ChatSession $session): array
    {
        return $session->messages()
            ->latest()
            ->limit(12)
            ->get()
            ->reverse()
            ->map(fn(ChatMessage $message) => [
                'role' => $message->role,
                'content' => $message->content,
                'created_at' => optional($message->created_at)->toIso8601String(),
            ])
            ->values()
            ->all();
    }

    private function detectAssets(string $message): array
    {
        $haystack = strtolower($message);
        $matches = [];

        foreach (TrackedMarketAsset::ASSETS as $symbol => $meta) {
            if (str_contains($haystack, strtolower($symbol))) {
                $matches[] = $symbol;
                continue;
            }

            foreach ($meta['keywords'] as $keyword) {
                if (str_contains($haystack, strtolower($keyword))) {
                    $matches[] = $symbol;
                    continue 2;
                }
            }
        }

        return array_values(array_unique($matches));
    }

    private function detectTopics(string $message): array
    {
        $haystack = strtolower($message);
        $topics = [];

        $dictionary = [
            'overview' => ['overview', 'dashboard', 'overall', 'summary', 'bias', 'sentiment', 'market'],
            'cot' => ['cot', 'commitment', 'cftc', 'non commercial', 'positioning'],
            'retail' => ['retail', 'broker', 'buyer', 'seller', 'fxssi'],
            'news' => ['news', 'article', 'headline', 'marketaux', 'latest news'],
            'fundamental' => ['fundamental', 'economic', 'event', 'forecast', 'actual', 'previous', 'country'],
            'trades' => ['trade', 'trades', 'journal', 'entry', 'exit', 'profit', 'loss', 'p/l', 'pl'],
        ];

        foreach ($dictionary as $topic => $keywords) {
            foreach ($keywords as $keyword) {
                if (str_contains($haystack, $keyword)) {
                    $topics[] = $topic;
                    break;
                }
            }
        }

        return array_values(array_unique($topics ?: ['overview']));
    }

    private function shouldInclude(array $topics, array $expected): bool
    {
        return !empty(array_intersect($topics, $expected));
    }

    private function safeCall(callable $callback): array
    {
        try {
            return [
                'included' => true,
                'data' => $callback(),
            ];
        } catch (Throwable $exception) {
            return [
                'included' => false,
                'error' => $exception->getMessage(),
            ];
        }
    }

    private function supportedOverviewAssets(): array
    {
        return array_flip(array_values(array_intersect(
            CotReport::supportedAssets(),
            RetailSentiment::supportedPairs()
        )));
    }

    private function isSupportedFundamentalPair(string $asset): bool
    {
        return in_array($asset, ['EURUSD', 'GBPUSD', 'AUDUSD', 'USDCAD', 'USDJPY'], true);
    }
}
