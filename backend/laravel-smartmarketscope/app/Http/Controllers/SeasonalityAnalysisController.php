<?php

namespace App\Http\Controllers;

use App\Http\Service\SeasonalityAnalysisService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Validator;
use RuntimeException;

class SeasonalityAnalysisController extends Controller
{
    public function __construct(private SeasonalityAnalysisService $seasonalityAnalysisService)
    {
    }

    public function index(Request $request): JsonResponse
    {
        ini_set('serialize_precision', '-1');

        $validator = Validator::make($request->all(), [
            'assets' => 'nullable',
            'period' => 'nullable|in:monthly,yearly',
            'years' => 'nullable|integer|min:5|max:30',
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
                'message' => 'Seasonality analysis retrieved successfully',
                'data' => $this->seasonalityAnalysisService->getSeasonality($request->all()),
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
