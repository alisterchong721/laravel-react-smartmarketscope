<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        if (DB::getDriverName() === 'sqlite') {
            return;
        }

        DB::statement('ALTER TABLE trade_records MODIFY entry_time DATETIME NOT NULL, MODIFY exit_time DATETIME NULL');
    }

    public function down(): void
    {
        if (DB::getDriverName() === 'sqlite') {
            return;
        }

        DB::statement('ALTER TABLE trade_records MODIFY entry_time TIMESTAMP NOT NULL, MODIFY exit_time TIMESTAMP NULL DEFAULT NULL');
    }
};
