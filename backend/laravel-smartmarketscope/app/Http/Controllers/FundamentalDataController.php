<?php

namespace App\Http\Controllers;

use App\Http\Controllers\Controller;
use App\Http\Service\FundamentalDataService;

use Illuminate\Http\Request;
use Illuminate\Http\JsonResponse;

class FundamentalDataController extends Controller
{
    protected $fundamentalDataService;

    public function __construct(FundamentalDataService $fundamentalDataService)
    {
        $this->fundamentalDataService = $fundamentalDataService;
    }

    public function getCountryLatestEvent(Request $request): JsonResponse
    {
        $country = $request->input('country');

        if (!$country) {
            return response()->json([
                'success' => false,
                'message' => 'Country parameter is required'
            ], 400);
        }

        $data = $this->fundamentalDataService->getCountryLatestEvent($country);

        if (!$data) {
            return response()->json([
                'success' => false,
                'message' => 'No data found'
            ], 404);
        }

        return response()->json($data, $data['success'] ? 200 : 404);
    }

    public function getEventCountryLatestData(Request $request): JsonResponse
    {
        $event = $request->input('event');
        $country = $request->input('country');
        $startDate = $request->input('start_date');
        $endDate = $request->input('end_date');

        $data = $this->fundamentalDataService->getEventCountryLatestData(
            $event,
            $country,
            $startDate,
            $endDate
        );

        if (empty($data)) {
            return response()->json([
                'success' => false,
                'message' => 'Something went wrong while retrieving the data',
                'data' => []
            ], 404);
        }

        return response()->json([
            'success' => true,
            'message' => 'Data Retrieved Successfully',
            'data' => $data
        ]);
    }

    public function calculatePairImpact(Request $request, $pair): JsonResponse
    {
        $pair = strtoupper($pair);

        $result = $this->fundamentalDataService->calculatePairImpact($pair);

        if (isset($result['error'])) {
            return response()->json([
                'success' => false,
                'message' => $result['error'],

            ], 404);
        }

        return response()->json([
            'success' => true,
            'data' => $result
        ]);
    }
}
