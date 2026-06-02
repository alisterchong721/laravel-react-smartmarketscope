<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::table('pending_user_registrations', function (Blueprint $table) {
            $table->unsignedTinyInteger('resend_count')->default(0)->after('code_hash');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::table('pending_user_registrations', function (Blueprint $table) {
            $table->dropColumn('resend_count');
        });
    }
};
