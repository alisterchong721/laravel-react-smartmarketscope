<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use App\Models\User;
use Carbon\Carbon;
use Carbon\CarbonInterface;

class TradeRecord extends Model
{
    use HasFactory;

    // Define the primary key (if different from default 'id')
    protected $primaryKey = 'trade_id';

    // Disable auto-incrementing if trade_id is not auto-increment
    public $incrementing = true;

    // Define the key type
    protected $keyType = 'int';

    // Define fillable columns for mass assignment
    protected $fillable = [
        'user_id',
        'asset_symbol',
        'direction',
        'entry_price',
        'exit_price',
        'entry_time',
        'exit_time',
        'profit_loss',
        'notes'
    ];

    // Define casts for specific columns
    protected $casts = [
        'entry_price' => 'decimal:6',
        'exit_price' => 'decimal:6',
        'profit_loss' => 'decimal:6',
        'entry_time' => 'datetime',
        'exit_time' => 'datetime',
        'created_at' => 'datetime',
        'updated_at' => 'datetime'
    ];

    /**
     * Define the relationship with User model
     * Each trade belongs to one user
     */
    public function user()
    {
        return $this->belongsTo(User::class, 'user_id');
    }

    protected function serializeDate(\DateTimeInterface $date): string
    {
        return (new \DateTimeImmutable($date->format('c')))
            ->setTimezone(new \DateTimeZone('UTC'))
            ->format('Y-m-d\TH:i:s\Z');
    }
}
