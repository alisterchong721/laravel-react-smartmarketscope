<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('cot_reports', function (Blueprint $table) {
            $table->id();
            $table->string('asset_symbol', 10);
            $table->date('report_date');
            $table->string('source_market_name');
            $table->string('source_contract_market_name')->nullable();
            $table->string('source_report_id')->nullable();
            $table->string('source_contract_code', 20)->nullable();
            $table->boolean('pair_is_inverse')->default(false);
            $table->unsignedBigInteger('open_interest_all')->nullable();

            $table->unsignedBigInteger('non_commercial_long')->nullable();
            $table->unsignedBigInteger('non_commercial_short')->nullable();
            $table->integer('non_commercial_change_long')->nullable();
            $table->integer('non_commercial_change_short')->nullable();
            $table->decimal('non_commercial_long_pct', 7, 2)->nullable();
            $table->decimal('non_commercial_short_pct', 7, 2)->nullable();

            $table->unsignedBigInteger('commercial_long')->nullable();
            $table->unsignedBigInteger('commercial_short')->nullable();
            $table->integer('commercial_change_long')->nullable();
            $table->integer('commercial_change_short')->nullable();
            $table->decimal('commercial_long_pct', 7, 2)->nullable();
            $table->decimal('commercial_short_pct', 7, 2)->nullable();

            $table->unsignedBigInteger('nonreportable_long')->nullable();
            $table->unsignedBigInteger('nonreportable_short')->nullable();
            $table->integer('nonreportable_change_long')->nullable();
            $table->integer('nonreportable_change_short')->nullable();
            $table->decimal('nonreportable_long_pct', 7, 2)->nullable();
            $table->decimal('nonreportable_short_pct', 7, 2)->nullable();

            $table->json('source_payload')->nullable();
            $table->timestamps();

            $table->unique(['asset_symbol', 'report_date']);
            $table->index('report_date');
            $table->index(['asset_symbol', 'report_date']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('cot_reports');
    }
};
