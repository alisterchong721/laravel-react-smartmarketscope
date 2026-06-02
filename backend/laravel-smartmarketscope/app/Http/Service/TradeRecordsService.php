<?php

namespace App\Http\Service;

use App\Models\TradeRecord;


class TradeRecordsService
{
    public function createTrade($data)
    {
        $required = [
            'user_id',
            'asset_symbol',
            'direction',
            'entry_price',
            'entry_time',
        ];

        foreach ($required as $field) {
            if (empty($data[$field])) {
                throw new \Exception("{$field} is required");
            }
        }

        return TradeRecord::create($data);
    }

    public function updateTrade($id, $userId, $data)
    {
        $trade = $this->findTradeForUser($id, $userId);
        $trade->update($data);
        return $trade;
    }

    public function getAllTrades($filters = [])
    {
        $query = TradeRecord::query();

        if (!empty($filters['user_id'])) {
            $query->where('user_id', $filters['user_id']);
        }

        if (!empty($filters['asset_symbol'])) {
            $query->where('asset_symbol', $filters['asset_symbol']);
        }

        if (!empty($filters['direction'])) {
            $query->where('direction', $filters['direction']);
        }

        return $query->get();
    }

    public function deleteTrade($id, $userId)
    {
        // $trade = TradeRecord::findOrFail($userId);
        // return TradeRecord::destroy($id);
        $trade = TradeRecord::where('trade_id', $id) // or 'id' depending on your column name
            ->where('user_id', $userId)
            ->delete();
        // ->limit(1);
        // $trade->destroy();
        return response()->json([
            'message' => 'Deleted Successfully',
            'success' => true
        ]);
    }

    public function findTradeForUser($id, $userId)
    {
        return TradeRecord::where('trade_id', $id)
            ->where('user_id', $userId)
            ->firstOrFail();
    }

 

    public function findTrade($id)
    {
        return TradeRecord::findOrFail($id);
    }

    public function findTradeByUser($userId)
    {
        if (empty($userId)) {
            throw new \Exception("User ID is required");
        }

        return TradeRecord::where('user_id', $userId)->get();
    }

    // ✅ ADD THIS: Get all trades with optional filters
  
}
