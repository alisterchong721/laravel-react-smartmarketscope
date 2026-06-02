<?php

namespace App\Http\Controllers;

use App\Http\Service\OverviewDashboardService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Validator;
use RuntimeException;

class OverviewDashboardController extends Controller
{
    public function __construct(private OverviewDashboardService $overviewDashboardService)
    {
    }

    public function index(Request $request): JsonResponse
    {
        ini_set('serialize_precision', '-1');

        $validator = Validator::make($request->all(), [
            'asset' => 'nullable|string|max:20',
            'assets' => 'nullable',
            'refresh' => 'nullable|boolean',
            'news_lookback_hours' => 'nullable|integer|min:1|max:168',
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
                'message' => 'Overview dashboard retrieved successfully',
                'data' => $this->overviewDashboardService->getOverview($request->all()),
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
        return response()->json([
            'success' => true,
            'message' => 'Overview dashboard filters retrieved successfully',
            'data' => $this->overviewDashboardService->getFiltersMeta(),
        ]);
    }
}
