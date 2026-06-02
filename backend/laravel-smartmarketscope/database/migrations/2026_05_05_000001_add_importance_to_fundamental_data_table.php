<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('fundamental_data', function (Blueprint $table) {
            if (!Schema::hasColumn('fundamental_data', 'importance')) {
                $table->string('importance', 20)->nullable()->after('impact');
                $table->index(['importance', 'date']);
            }
        });
    }

    public function down(): void
    {
        Schema::table('fundamental_data', function (Blueprint $table) {
            if (Schema::hasColumn('fundamental_data', 'importance')) {
                $table->dropIndex(['importance', 'date']);
                $table->dropColumn('importance');
            }
        });
    }
};
