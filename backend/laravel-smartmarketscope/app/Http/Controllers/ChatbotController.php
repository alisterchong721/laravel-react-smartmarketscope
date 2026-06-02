<?php

namespace App\Http\Controllers;

use App\Http\Service\ChatbotService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Throwable;

class ChatbotController extends Controller
{
    public function __construct(private ChatbotService $chatbotService)
    {
    }

    public function message(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'message' => ['required', 'string', 'max:2000'],
            'session_id' => ['nullable', 'integer'],
        ]);

        try {
            return response()->json([
                'success' => true,
                'message' => 'Chatbot response generated successfully',
                'data' => $this->chatbotService->reply(
                    $request->user(),
                    $validated['message'],
                    $validated['session_id'] ?? null
                ),
            ]);
        } catch (Throwable $exception) {
            return response()->json([
                'success' => false,
                'message' => $exception->getMessage(),
                'data' => [],
            ], 400);
        }
    }
}
