<?php

namespace App\Http\Controllers;

use App\Http\Service\CotReportService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Validator;
use RuntimeException;

class CotReportController extends Controller
{
    public function __construct(private CotReportService $cotReportService)
    {
    }

    public function index(Request $request): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'asset' => 'nullable|string|max:20',
            'assets' => 'nullable',
            'report_date' => 'nullable|date',
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
                'message' => 'COT sentiment retrieved successfully',
                'data' => $this->cotReportService->getCotReport($request->all()),
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
                'message' => 'COT sentiment filters retrieved successfully',
                'data' => $this->cotReportService->getFiltersMeta(),
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
