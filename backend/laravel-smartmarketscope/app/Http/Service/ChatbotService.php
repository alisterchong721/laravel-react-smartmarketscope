<?php

namespace App\Http\Service;

use App\Models\ChatMessage;
use App\Models\ChatSession;
use App\Models\User;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use RuntimeException;

class ChatbotService
{
    public function __construct(private ChatbotContextService $contextService)
    {
    }

    public function reply(User $user, string $message, ?int $sessionId = null): array
    {
        $apiKey = config('services.openai.api_key');

        if (!$apiKey) {
            throw new RuntimeException('OPENAI_API_KEY is not configured.');
        }

        $session = $this->resolveSession($user, $sessionId, $message);
        $userMessage = $this->storeMessage($session, $user, ChatMessage::ROLE_USER, $message);
        $context = $this->contextService->build($user, $message, $session);
        $responsePayload = $this->callOpenAi($message, $context);
        $answer = $this->extractOutputText($responsePayload);

        if (!$answer) {
            throw new RuntimeException('OpenAI did not return a chatbot response.');
        }

        $assistantMessage = $this->storeMessage(
            $session,
            $user,
            ChatMessage::ROLE_ASSISTANT,
            $answer,
            [
                'context_generated_at' => $context['generated_at'] ?? null,
                'question_analysis' => $context['question_analysis'] ?? [],
                'site_data_status' => $this->siteDataStatus($context),
            ],
            $responsePayload['id'] ?? null
        );

        $session->update(['last_message_at' => now()]);

        return [
            'session_id' => $session->id,
            'user_message' => $this->formatMessage($userMessage),
            'assistant_message' => $this->formatMessage($assistantMessage),
            'context_status' => $assistantMessage->metadata['site_data_status'] ?? [],
        ];
    }

    private function resolveSession(User $user, ?int $sessionId, string $message): ChatSession
    {
        if ($sessionId) {
            $session = ChatSession::query()
                ->where('user_id', $user->id)
                ->whereKey($sessionId)
                ->first();

            if ($session) {
                return $session;
            }
        }

        return ChatSession::query()->create([
            'user_id' => $user->id,
            'title' => mb_substr($message, 0, 80),
            'last_message_at' => now(),
        ]);
    }

    private function storeMessage(
        ChatSession $session,
        User $user,
        string $role,
        string $content,
        array $metadata = [],
        ?string $openAiResponseId = null
    ): ChatMessage {
        return DB::transaction(function () use ($session, $user, $role, $content, $metadata, $openAiResponseId) {
            return ChatMessage::query()->create([
                'chat_session_id' => $session->id,
                'user_id' => $user->id,
                'role' => $role,
                'content' => $content,
                'metadata' => $metadata ?: null,
                'openai_response_id' => $openAiResponseId,
            ]);
        });
    }

    private function callOpenAi(string $message, array $context): array
    {
        $response = Http::withToken(config('services.openai.api_key'))
            ->acceptJson()
            ->timeout((int) config('services.openai.timeout', 45))
            ->post(config('services.openai.endpoint'), [
                'model' => config('services.openai.chatbot_model', config('services.openai.model', 'gpt-5-nano')),
                'input' => [
                    [
                        'role' => 'system',
                        'content' => [
                            [
                                'type' => 'input_text',
                                'text' => $this->systemPrompt(),
                            ],
                        ],
                    ],
                    [
                        'role' => 'user',
                        'content' => [
                            [
                                'type' => 'input_text',
                                'text' => json_encode([
                                    'latest_context' => $context,
                                    'current_user_question' => $message,
                                ], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES),
                            ],
                        ],
                    ],
                ],
            ]);

        if ($response->failed()) {
            throw new RuntimeException('OpenAI chatbot request failed: ' . $response->body());
        }

        return $response->json() ?? [];
    }

    private function systemPrompt(): string
    {
        return <<<'PROMPT'
You are the SmartMarketScope assistant inside a trading dashboard.

Answer only questions related to SmartMarketScope, including dashboard navigation, overview bias, fundamentals, COT sentiment, retail sentiment, news sentiment, and the logged-in user's trading journal.

Grounding rules:
1. Use only the provided latest_context and recent_conversation.
2. Never invent market data, trade records, news, prices, report dates, or unavailable facts.
3. Do not present normal dashboard scale conversions or intentionally omitted unrelated sources as problems, caveats, missing details, discrepancies, or site issues.
4. If the user asks about fundamentals, explain the pair_score, base_score, quote_score, impact label, dashboard score scale, and the latest base/quote country events included in context.
5. Only mention missing or errored data when it directly prevents answering the user's question, or when the user explicitly asks about limitations/data availability.
6. When explaining market bias, mention which site signals support it.
7. Do not give direct financial advice or instructions to buy/sell. You may explain signals, risks, confluence, and data limitations.
8. Keep answers concise, clear, and helpful for a dashboard user.
9. Present data in user-facing language. Do not mention raw database fields, internal IDs, snake_case keys, JSON paths, or API field names unless the user explicitly asks for technical details.
10. For trading journal answers, describe trades by asset, direction, entry/exit, result, and P/L. Do not say "trade_id"; use phrases like "the USDJPY sell trade" or "the latest EURUSD buy trade."
11. Use Malaysia time labels from the context when discussing dates or times. Do not output ISO timestamps.
12. If a journal timestamp looks inconsistent, explain it gently as "please check this journal entry" rather than exposing raw data.
PROMPT;
    }

    private function extractOutputText(array $payload): ?string
    {
        if (!empty($payload['output_text']) && is_string($payload['output_text'])) {
            return $payload['output_text'];
        }

        foreach ($payload['output'] ?? [] as $outputItem) {
            foreach ($outputItem['content'] ?? [] as $contentItem) {
                if (($contentItem['type'] ?? null) === 'output_text' && !empty($contentItem['text'])) {
                    return $contentItem['text'];
                }
            }
        }

        return null;
    }

    private function siteDataStatus(array $context): array
    {
        $status = [];

        foreach (($context['latest_site_data'] ?? []) as $source => $payload) {
            $status[$source] = [
                'included' => (bool) ($payload['included'] ?? false),
                'error' => $payload['error'] ?? null,
                'reason' => $payload['reason'] ?? null,
            ];
        }

        return $status;
    }

    private function formatMessage(ChatMessage $message): array
    {
        return [
            'id' => $message->id,
            'role' => $message->role,
            'content' => $message->content,
            'metadata' => $message->metadata,
            'created_at' => optional($message->created_at)->toIso8601String(),
        ];
    }
}
