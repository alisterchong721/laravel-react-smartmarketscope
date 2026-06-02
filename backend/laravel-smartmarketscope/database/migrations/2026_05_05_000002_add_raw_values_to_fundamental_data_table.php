<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('fundamental_data', function (Blueprint $table) {
            if (!Schema::hasColumn('fundamental_data', 'actual_raw')) {
                $table->string('actual_raw', 40)->nullable()->after('actual');
            }

            if (!Schema::hasColumn('fundamental_data', 'forecast_raw')) {
                $table->string('forecast_raw', 40)->nullable()->after('forecast');
            }

            if (!Schema::hasColumn('fundamental_data', 'previous_raw')) {
                $table->string('previous_raw', 40)->nullable()->after('previous');
            }
        });
    }

    public function down(): void
    {
        Schema::table('fundamental_data', function (Blueprint $table) {
            foreach (['actual_raw', 'forecast_raw', 'previous_raw'] as $column) {
                if (Schema::hasColumn('fundamental_data', $column)) {
                    $table->dropColumn($column);
                }
            }
        });
    }
};
