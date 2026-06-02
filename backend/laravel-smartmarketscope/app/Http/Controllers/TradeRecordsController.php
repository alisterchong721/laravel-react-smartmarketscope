<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Http\Service\TradeRecordsService;
use Illuminate\Support\Facades\Validator;
use Carbon\Carbon;

class TradeRecordsController extends Controller
{
    //

    protected $tradeRecordsService;

    public function __construct(TradeRecordsService $tradeRecordsService)
    {
        $this->tradeRecordsService = $tradeRecordsService;
    }

    public function createTrade(Request $request)
    {
        try {
            // Simple validation
            $validator = Validator::make($request->all(), [
                'user_id' => 'required|integer|exists:users,id',
                'asset_symbol' => 'required|string|max:20',
                'direction' => 'required|in:BUY,SELL,LONG,SHORT',
                'entry_price' => 'required|numeric|min:0.000001',
                'entry_time' => 'required|date',
                'exit_price' => 'nullable|numeric|min:0.000001',
                'exit_time' => 'nullable|date|after_or_equal:entry_time',
                'profit_loss' => 'nullable|numeric',
                'notes' => 'nullable|string|max:1000'
            ]);

            if ($validator->fails()) {
                return response()->json([
                    'success' => false,
                    'message' => 'Validation failed',
                    'errors' => $validator->errors()
                ], 422);
            }

            $trade = $this->tradeRecordsService->createTrade($request->all());

            return response()->json([
                'success' => true,
                'message' => 'Trade created successfully',
                'data' => $trade
            ], 201);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => $e->getMessage(),
                'data' => []
            ], 400);
        }
    }

    /**
     * Update an existing trade
     */
    // In your Controller
    public function updateTrade(Request $request)
    {
        try {
            $id = $request->input('id');
            $user_id = $request->input('user_id');

            if (!$id) {
                return response()->json([
                    'success' => false,
                    'message' => 'id parameter is required'
                ], 400);
            }

            if (!$user_id) {
                return response()->json([
                    'success' => false,
                    'message' => 'user_id parameter is required'
                ], 400);
            }

            $existingTrade = $this->tradeRecordsService->findTradeForUser($id, $user_id);

            // Validation for update - IMPORTANT: Handle nullable fields properly
            $validator = Validator::make($request->all(), [
                'asset_symbol' => 'sometimes|string|max:20',
                'direction' => 'sometimes|in:BUY,SELL,LONG,SHORT',
                'entry_price' => 'sometimes|numeric|min:0.000001',
                'entry_time' => 'sometimes|date',
                'exit_price' => 'nullable|numeric|min:0.000001',
                'exit_time' => [
                    'nullable',
                    'date',
                    function ($attribute, $value, $fail) use ($request, $existingTrade) {
                        $entryTime = $request->input('entry_time', $existingTrade->entry_time);

                        if ($value && $entryTime) {
                            $exit  = Carbon::parse($value);
                            $entry = Carbon::parse($entryTime);

                            if ($exit->lt($entry)) {
                                $fail('Exit time must be after or equal to entry time.');
                            }
                        }
                    }
                ],
                'profit_loss' => 'nullable|numeric',
                'notes' => 'nullable|string|max:1000'
            ]);

            if ($validator->fails()) {
                return response()->json([
                    'success' => false,
                    'message' => 'Validation failed',
                    'errors' => $validator->errors()
                ], 422);
            }

            // Prepare the data for update. Only include fields the client
            // actually sent; missing timestamp fields must not be updated as
            // null because MySQL TIMESTAMP can coerce null to current time.
            $allowedFields = [
                'asset_symbol',
                'direction',
                'entry_price',
                'entry_time',
                'exit_price',
                'exit_time',
                'profit_loss',
                'notes'
            ];

            $data = [];
            foreach ($allowedFields as $field) {
                if ($request->exists($field)) {
                    $data[$field] = $request->input($field);
                }
            }

            // Convert empty strings to null for nullable fields
            $nullableFields = ['exit_price', 'exit_time', 'profit_loss', 'notes'];
            foreach ($nullableFields as $field) {
                if (isset($data[$field]) && $data[$field] === '') {
                    $data[$field] = null;
                }
            }

            // If exit_time is being updated to null, ensure exit_price is also null
            if (array_key_exists('exit_time', $data) && is_null($data['exit_time'])) {
                $data['exit_price'] = null;
                $data['profit_loss'] = null;
            }

            $trade = $this->tradeRecordsService->updateTrade($id, $user_id, $data);

            return response()->json([
                'success' => true,
                'message' => 'Trade updated successfully',
                'data' => $trade
            ]);
        } catch (\Illuminate\Database\Eloquent\ModelNotFoundException $e) {
            return response()->json([
                'success' => false,
                'message' => 'Trade not found or you do not have permission to update it',
                'data' => []
            ], 404);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => $e->getMessage(),
                'data' => []
            ], 400);
        }
    }

    public function deleteTrade(Request $request)
    {
        try {
            $id = $request->input('id');
            $userId = $request->input('user_id');
            if (!$id) {
                return response()->json([
                    'success' => false,
                    'message' => 'id parameter is required'
                ], 400);
            }

            $data = $this->tradeRecordsService->deleteTrade($id, $userId);

            if (empty($data)) {
                return response()->json([
                    'success' => false,
                    'message' => 'Something went wrong while deleting the data',
                    'data' => []
                ], 404);
            }
        } catch (\Illuminate\Database\Eloquent\ModelNotFoundException $e) {
            return response()->json([
                'success' => false,
                'message' => 'Trade not found or you do not have permission to delete it',
                'data' => []
            ], 404);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => $e->getMessage(),
                'data' => []
            ], 400);
        }
        return response()->json([
            'success' => true,
            'message' => 'Data Deleted Successfully',
            'data_id' => $id
        ]);
    }

    public function findTrade(Request $request)
    {
        $id = $request->input('id');
        if (!$id) {
            return response()->json([
                'success' => false,
                'message' => 'id parameter is required'
            ], 400);
        }

        $data = $this->tradeRecordsService->findTrade($id);

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

    public function findTradeByuser(Request $request)
    {
        $userId = $request->input('user_id');
        if (empty($userId)) {
            return response()->json([
                'success' => false,
                'message' => 'user_id parameter is required'
            ], 404);
        }

        $data = $this->tradeRecordsService->findTradeByUser($userId);

        if (empty($data)) {
            return response()->json([
                'success' => false,
                'message' => 'Something went wrong while retrieving the data',
                'data' => []
            ], 404);
        }

        return response()->json([
            'success' => true,
            'message' => 'Data retrieved successfully',
            'data' => $data
        ]);
    }

    public function getAllTrades(Request $request)
    {
        try {
            // Get filters from request
            $filters = $request->only(['user_id', 'asset_symbol', 'direction']);

            // Add direction filter if provided
            if ($request->has('direction')) {
                $validDirections = ['BUY', 'SELL', 'LONG', 'SHORT'];
                if (!in_array($request->direction, $validDirections)) {
                    return response()->json([
                        'success' => false,
                        'message' => 'Invalid direction. Use: BUY, SELL, LONG, SHORT'
                    ], 400);
                }
                $filters['direction'] = $request->direction;
            }

            $trades = $this->tradeRecordsService->getAllTrades($filters);

            return response()->json([
                'success' => true,
                'message' => 'Trades retrieved successfully',
                'data' => $trades,
                'count' => count($trades),
                'filters_applied' => !empty($filters) ? $filters : 'none'
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => $e->getMessage(),
                'data' => []
            ], 500);
        }
    }
}
