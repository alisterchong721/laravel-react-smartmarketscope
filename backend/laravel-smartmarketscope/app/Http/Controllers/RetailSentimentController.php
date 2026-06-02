<?php

namespace App\Http\Controllers;

use App\Http\Service\RetailSentimentService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Validator;
use RuntimeException;

class RetailSentimentController extends Controller
{
    public function __construct(private RetailSentimentService $retailSentimentService)
    {
    }

    public function index(Request $request): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'group_by' => 'nullable|in:pairs,brokers',
            'pair' => 'nullable|string|max:20',
            'broker' => 'nullable|string|max:50',
            'pairs' => 'nullable',
            'brokers' => 'nullable',
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
            $data = $this->retailSentimentService->getRetailSentiment($request->all());

            return response()->json([
                'success' => true,
                'message' => 'Retail sentiment retrieved successfully',
                'data' => $data,
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
                'message' => 'Retail sentiment filters retrieved successfully',
                'data' => $this->retailSentimentService->getFiltersMeta(),
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
