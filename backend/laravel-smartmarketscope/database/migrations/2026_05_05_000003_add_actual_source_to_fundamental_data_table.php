<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('fundamental_data', function (Blueprint $table) {
            if (!Schema::hasColumn('fundamental_data', 'actual_source')) {
                $table->string('actual_source', 80)->nullable()->after('actual_raw');
            }

            if (!Schema::hasColumn('fundamental_data', 'actual_synced_at')) {
                $table->timestamp('actual_synced_at')->nullable()->after('actual_source');
            }
        });
    }

    public function down(): void
    {
        Schema::table('fundamental_data', function (Blueprint $table) {
            foreach (['actual_synced_at', 'actual_source'] as $column) {
                if (Schema::hasColumn('fundamental_data', $column)) {
                    $table->dropColumn($column);
                }
            }
        });
    }
};
