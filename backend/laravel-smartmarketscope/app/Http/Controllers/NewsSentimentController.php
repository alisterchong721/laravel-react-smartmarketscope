<?php

namespace App\Http\Controllers;

use App\Http\Service\NewsSentimentService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Validator;
use RuntimeException;

class NewsSentimentController extends Controller
{
    public function __construct(private NewsSentimentService $newsSentimentService)
    {
    }

    public function index(Request $request): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'asset' => 'nullable|string|max:20',
            'assets' => 'nullable',
            'direction' => 'nullable|in:bullish,bearish,neutral',
            'status' => 'nullable|in:completed,pending,failed',
            'from_date' => 'nullable|date',
            'to_date' => 'nullable|date',
            'min_impact_score' => 'nullable|integer|min:0|max:100',
            'limit' => 'nullable|integer|min:1|max:100',
            'refresh' => 'nullable|boolean',
        ]);

        if ($validator->fails()) {
            return response()->json([
                'success' => false,
                'message' => 'Validation failed',
                'errors' => $validator->errors(),
            ], 422);
        }

        try {
            return response()->json([
                'success' => true,
                'message' => 'News sentiment retrieved successfully',
                'data' => $this->newsSentimentService->getNewsSentiment($request->all()),
            ]);
        } catch (RuntimeException $exception) {
            return response()->json([
                'success' => false,
                'message' => $exception->getMessage(),
                'data' => [],
            ], 502);
        }
    }

    public function filters(): JsonResponse
    {
        try {
            return response()->json([
                'success' => true,
                'message' => 'News sentiment filters retrieved successfully',
                'data' => $this->newsSentimentService->getFiltersMeta(),
            ]);
        } catch (RuntimeException $exception) {
            return response()->json([
                'success' => false,
                'message' => $exception->getMessage(),
                'data' => [],
            ], 502);
        }
    }

    public function sourceNews(Request $request): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'lookback_hours' => 'nullable|integer|min:1|max:168',
            'limit' => 'nullable|integer|min:1|max:100',
        ]);

        if ($validator->fails()) {
            return response()->json([
                'success' => false,
                'message' => 'Validation failed',
                'errors' => $validator->errors(),
            ], 422);
        }

        try {
            return response()->json([
                'success' => true,
                'message' => 'Source news preview retrieved successfully',
                'data' => $this->newsSentimentService->getSourceNewsPreview($request->all()),
            ]);
        } catch (RuntimeException $exception) {
            return response()->json([
                'success' => false,
                'message' => $exception->getMessage(),
                'data' => [],
            ], 502);
        }
    }

    public function fetchedNews(Request $request): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'status' => 'nullable|in:completed,pending,failed',
            'from_date' => 'nullable|date',
            'to_date' => 'nullable|date',
            'limit' => 'nullable|integer|min:1|max:100',
        ]);

        if ($validator->fails()) {
            return response()->json([
                'success' => false,
                'message' => 'Validation failed',
                'errors' => $validator->errors(),
            ], 422);
        }

        try {
            return response()->json([
                'success' => true,
                'message' => 'Fetched news retrieved successfully',
                'data' => $this->newsSentimentService->getFetchedNews($request->all()),
            ]);
        } catch (RuntimeException $exception) {
            return response()->json([
                'success' => false,
                'message' => $exception->getMessage(),
                'data' => [],
            ], 502);
        }
    }

    public function sync(Request $request): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'refresh' => 'nullable|boolean',
        ]);

        if ($validator->fails()) {
            return response()->json([
                'success' => false,
                'message' => 'Validation failed',
                'errors' => $validator->errors(),
            ], 422);
        }

        try {
            return response()->json([
                'success' => true,
                'message' => 'News sentiment sync started successfully',
                'data' => $this->newsSentimentService->syncLatestData((bool) ($request->boolean('refresh', true))),
            ]);
        } catch (RuntimeException $exception) {
            return response()->json([
                'success' => false,
                'message' => $exception->getMessage(),
                'data' => [],
            ], 502);
        }
    }
}
