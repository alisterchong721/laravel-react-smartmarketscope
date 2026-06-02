<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('trade_records', function (Blueprint $table) {
            $table->id('trade_id');
            $table->unsignedBigInteger('user_id'); // Foreign key
            
            $table->string('asset_symbol', 20);
            $table->enum('direction', ['BUY', 'SELL', 'LONG', 'SHORT']);
            $table->decimal('entry_price', 15, 6);
            $table->decimal('exit_price', 15, 6)->nullable();
            $table->timestamp('entry_time');
            $table->timestamp('exit_time')->nullable();
            $table->decimal('profit_loss', 15, 6)->nullable();
            $table->text('notes')->nullable();
            
            // Foreign key constraint
            $table->foreign('user_id')
                  ->references('id')
                  ->on('users')
                  ->onDelete('cascade'); // Or onDelete('restrict')
            
            $table->timestamps(); // created_at, updated_at
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('trade_records');
    }
};