<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('news_articles', function (Blueprint $table) {
            $table->id();
            $table->string('provider', 50);
            $table->string('provider_article_id', 120)->nullable();
            $table->string('source_name')->nullable();
            $table->string('title');
            $table->text('summary')->nullable();
            $table->text('snippet')->nullable();
            $table->text('url');
            $table->string('url_hash', 64)->unique();
            $table->text('image_url')->nullable();
            $table->string('language', 10)->nullable();
            $table->timestamp('published_at')->nullable();
            $table->timestamp('fetched_at')->nullable();
            $table->string('analysis_status', 20)->default('pending');
            $table->string('summary_sentiment', 20)->nullable();
            $table->string('market_theme')->nullable();
            $table->unsignedSmallInteger('global_impact_score')->nullable();
            $table->timestamp('analyzed_at')->nullable();
            $table->text('analysis_error')->nullable();
            $table->json('analysis_payload')->nullable();
            $table->json('raw_payload')->nullable();
            $table->timestamps();

            $table->unique(['provider', 'provider_article_id']);
            $table->index(['analysis_status', 'published_at']);
            $table->index('published_at');
        });

        Schema::create('news_article_asset_impacts', function (Blueprint $table) {
            $table->id();
            $table->foreignId('news_article_id')->constrained('news_articles')->cascadeOnDelete();
            $table->string('asset_symbol', 10);
            $table->string('display_name');
            $table->string('direction', 20);
            $table->string('sentiment_label')->nullable();
            $table->unsignedSmallInteger('impact_score')->default(0);
            $table->unsignedSmallInteger('confidence_score')->default(0);
            $table->text('reasoning')->nullable();
            $table->string('market_theme')->nullable();
            $table->json('tags')->nullable();
            $table->decimal('provider_entity_sentiment', 8, 4)->nullable();
            $table->string('model_name')->nullable();
            $table->timestamp('published_at')->nullable();
            $table->timestamp('analyzed_at')->nullable();
            $table->json('analysis_payload')->nullable();
            $table->timestamps();

            $table->unique(['news_article_id', 'asset_symbol']);
            $table->index(['asset_symbol', 'published_at']);
            $table->index(['direction', 'impact_score']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('news_article_asset_impacts');
        Schema::dropIfExists('news_articles');
    }
};
