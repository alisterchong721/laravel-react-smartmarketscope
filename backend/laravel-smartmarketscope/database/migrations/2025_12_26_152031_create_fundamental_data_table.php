<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('fundamental_data', function (Blueprint $table) {
            $table->id();
            $table->string('country')->nullable();
            $table->string('event');
            $table->string('currency', 3)->nullable();
            $table->decimal('actual', 12, 6)->nullable();
            $table->decimal('forecast', 12, 6)->nullable();
            $table->decimal('previous', 12, 6)->nullable();
            
            // ✅ CORRECT: Create column FIRST
            $table->string('impact', 15)->default('Neutral');
            
            $table->date('date');
            $table->time('time')->nullable();
            $table->string('source')->nullable();
            $table->timestamps();

            // ✅ CORRECT: Add indexes AFTER columns are defined
            $table->index(['country', 'date']);
            $table->index(['event', 'date']);
            $table->index(['date', 'impact']); // This works now
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('fundamental_data');
    }
};