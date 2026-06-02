<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Http\Service\FundamentalScrapeService;
use Symfony\Component\HttpFoundation\JsonResponse;

class FundamentalScrapeController extends Controller
{
    private $fundamentalSrapeService;

    public function __construct(FundamentalScrapeService $fundamentalSrapeService)
    {
        $this->fundamentalSrapeService = $fundamentalSrapeService;
    }

    public function viewData(Request $request): JsonResponse
    {
        $seriesId = $request->input('series_id');
        $units = $request->input('units');

        // Get data from service
        $result = $this->fundamentalSrapeService->viewData($seriesId, $units);

        if (isset($result['error'])) {
            return response()->json([
                'success' => false,
                'error' => $result['message'],
            ], 500);
        }

        // Return as JSON
        return response()->json([
            'success' => true,
            'series_id' => $seriesId,
            'data_count' => $result['data_count'],
            'units' => $units,
            'sample' => $result['observations']
        ]);
    }

    public function storeData(Request $request): JsonResponse
    {
        $seriesId = $request->input('series_id');
        $units = $request->input('units');

        $result = $this->fundamentalSrapeService->storeData($seriesId, $units);

        if (isset($result['error'])) {
            return response()->json([
                'success' => false,
                'error' => $result['message'],
                'errors' => $result['errors'] ?? [], // ✅ Show specific errors
                'valid_count' => $result['valid_count'] ?? 0,
                'error_count' => $result['error_count'] ?? 0,
                'total_observations' => $result['total_observations'] ?? 0,
                'note' => $result['note'] ?? 'No data stored',
            ], 400);
        }

        return response()->json([
            'success' => true,
            'message' => $result['message'] ?? 'Success',
            'stats' => $result['stats'] ?? [],
            'date_range' => $result['date_range'] ?? '2020-01-01 to 2025-12-31',
            'first_record' => $result['first_record'] ?? null,
            'last_record' => $result['last_record'] ?? null,
            'data_quality' => $result['data_quality'] ?? null,
            'missing_dates' => $result['missing_dates'] ?? [],
            'note' => $result['note'] ?? 'Data stored',
        ]);
    }

    public function syncCalendar(Request $request): JsonResponse
    {
        $periods = $request->input('periods');
        $impacts = $request->input('impacts');

        $periods = is_string($periods) ? array_filter(array_map('trim', explode(',', $periods))) : $periods;
        $impacts = is_string($impacts) ? array_filter(array_map('trim', explode(',', $impacts))) : $impacts;

        try {
            $result = $this->fundamentalSrapeService->syncForexFactoryCalendar(
                is_array($periods) ? $periods : null,
                is_array($impacts) ? $impacts : null
            );
        } catch (\Throwable $exception) {
            return response()->json([
                'success' => false,
                'error' => $exception->getMessage(),
            ], 502);
        }

        return response()->json($result);
    }

    public function calendar(Request $request): JsonResponse
    {
        return response()->json([
            'success' => true,
            'data' => $this->fundamentalSrapeService->getForexFactoryCalendar($request->all()),
        ]);
    }
}
