<?php

namespace Tests\Feature;

use App\Models\CotReport;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class CotReportApiTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_syncs_latest_cot_data_and_returns_all_three_categories(): void
    {
        Http::fake([
            'https://publicreporting.cftc.gov/resource/6dca-aqww.json*' => Http::sequence()
                ->push([
                    ['report_date_as_yyyy_mm_dd' => '2026-03-24T00:00:00.000'],
                ], 200)
                ->push([
                    [
                        'id' => 'row-eurusd',
                        'market_and_exchange_names' => 'EURO FX - CHICAGO MERCANTILE EXCHANGE',
                        'contract_market_name' => 'EURO FX',
                        'cftc_contract_market_code' => '099741',
                        'report_date_as_yyyy_mm_dd' => '2026-03-24T00:00:00.000',
                        'open_interest_all' => '886502',
                        'noncomm_positions_long_all' => '172992',
                        'noncomm_positions_short_all' => '204344',
                        'comm_positions_long_all' => '543831',
                        'comm_positions_short_all' => '550267',
                        'nonrept_positions_long_all' => '90211',
                        'nonrept_positions_short_all' => '52423',
                        'change_in_noncomm_long_all' => '2300',
                        'change_in_noncomm_short_all' => '-1400',
                        'change_in_comm_long_all' => '5000',
                        'change_in_comm_short_all' => '4200',
                        'change_in_nonrept_long_all' => '120',
                        'change_in_nonrept_short_all' => '-85',
                        'pct_of_oi_noncomm_long_all' => '19.5',
                        'pct_of_oi_noncomm_short_all' => '23.1',
                        'pct_of_oi_comm_long_all' => '61.3',
                        'pct_of_oi_comm_short_all' => '62.1',
                        'pct_of_oi_nonrept_long_all' => '10.2',
                        'pct_of_oi_nonrept_short_all' => '5.9',
                    ],
                    [
                        'id' => 'row-usdjpy',
                        'market_and_exchange_names' => 'JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE',
                        'contract_market_name' => 'JAPANESE YEN',
                        'cftc_contract_market_code' => '097741',
                        'report_date_as_yyyy_mm_dd' => '2026-03-24T00:00:00.000',
                        'open_interest_all' => '324743',
                        'noncomm_positions_long_all' => '97792',
                        'noncomm_positions_short_all' => '163287',
                        'comm_positions_long_all' => '182675',
                        'comm_positions_short_all' => '123434',
                        'nonrept_positions_long_all' => '44276',
                        'nonrept_positions_short_all' => '38022',
                        'change_in_noncomm_long_all' => '1500',
                        'change_in_noncomm_short_all' => '-2000',
                        'change_in_comm_long_all' => '-700',
                        'change_in_comm_short_all' => '900',
                        'change_in_nonrept_long_all' => '55',
                        'change_in_nonrept_short_all' => '-75',
                        'pct_of_oi_noncomm_long_all' => '30.1',
                        'pct_of_oi_noncomm_short_all' => '50.3',
                        'pct_of_oi_comm_long_all' => '56.3',
                        'pct_of_oi_comm_short_all' => '38.0',
                        'pct_of_oi_nonrept_long_all' => '13.6',
                        'pct_of_oi_nonrept_short_all' => '11.7',
                    ],
                ], 200)
                ->push([], 200),
        ]);

        $response = $this->getJson('/api/cot-sentiment');

        $response->assertOk()
            ->assertJsonPath('success', true)
            ->assertJsonPath('data.report_date', '2026-03-24')
            ->assertJsonPath('data.source.latest_source_report_date', '2026-03-24')
            ->assertJsonCount(2, 'data.items');

        $response->assertJsonPath('data.items.0.asset_symbol', 'EURUSD');
        $response->assertJsonPath('data.items.0.categories.non_commercial.long_contracts', 172992);
        $response->assertJsonPath('data.items.0.categories.non_commercial.short_contracts', 204344);

        $response->assertJsonPath('data.items.1.asset_symbol', 'USDJPY');
        $response->assertJsonPath('data.items.1.pair_is_inverse', true);
        $response->assertJsonPath('data.items.1.categories.non_commercial.long_contracts', 163287);
        $response->assertJsonPath('data.items.1.categories.non_commercial.short_contracts', 97792);

        $this->assertDatabaseCount('cot_reports', 2);
    }

    public function test_it_returns_database_data_when_latest_report_is_already_stored(): void
    {
        CotReport::query()->create([
            'asset_symbol' => 'EURUSD',
            'report_date' => '2026-03-24',
            'source_market_name' => 'EURO FX - CHICAGO MERCANTILE EXCHANGE',
            'source_contract_market_name' => 'EURO FX',
            'source_report_id' => 'row-eurusd',
            'source_contract_code' => '099741',
            'pair_is_inverse' => false,
            'open_interest_all' => 886502,
            'non_commercial_long' => 172992,
            'non_commercial_short' => 204344,
            'non_commercial_change_long' => 2300,
            'non_commercial_change_short' => -1400,
            'non_commercial_long_pct' => 19.5,
            'non_commercial_short_pct' => 23.1,
            'commercial_long' => 543831,
            'commercial_short' => 550267,
            'commercial_change_long' => 5000,
            'commercial_change_short' => 4200,
            'commercial_long_pct' => 61.3,
            'commercial_short_pct' => 62.1,
            'nonreportable_long' => 90211,
            'nonreportable_short' => 52423,
            'nonreportable_change_long' => 120,
            'nonreportable_change_short' => -85,
            'nonreportable_long_pct' => 10.2,
            'nonreportable_short_pct' => 5.9,
            'source_payload' => [],
        ]);

        Http::fake([
            'https://publicreporting.cftc.gov/resource/6dca-aqww.json*' => Http::response([
                ['report_date_as_yyyy_mm_dd' => '2026-03-24T00:00:00.000'],
            ], 200),
        ]);

        $response = $this->getJson('/api/cot-sentiment?asset=EURUSD');

        $response->assertOk()
            ->assertJsonPath('success', true)
            ->assertJsonPath('data.synced_from_source', false)
            ->assertJsonPath('data.sync_mode', 'database_only')
            ->assertJsonPath('data.items.0.asset_symbol', 'EURUSD');
    }

    public function test_force_refresh_reimports_latest_stored_report_date(): void
    {
        CotReport::query()->create([
            'asset_symbol' => 'EURUSD',
            'report_date' => '2026-06-09',
            'source_market_name' => 'EURO FX - CHICAGO MERCANTILE EXCHANGE',
            'source_contract_market_name' => 'EURO FX',
            'source_report_id' => 'old-combined-row',
            'source_contract_code' => '099741',
            'pair_is_inverse' => false,
            'open_interest_all' => 1015246,
            'non_commercial_long' => 199791,
            'non_commercial_short' => 218136,
            'non_commercial_change_long' => -10655,
            'non_commercial_change_short' => 23418,
            'non_commercial_long_pct' => 19.7,
            'non_commercial_short_pct' => 21.5,
            'commercial_long' => 606982,
            'commercial_short' => 613929,
            'commercial_change_long' => 32629,
            'commercial_change_short' => 1882,
            'commercial_long_pct' => 59.8,
            'commercial_short_pct' => 60.5,
            'nonreportable_long' => 94784,
            'nonreportable_short' => 69492,
            'nonreportable_change_long' => 3883,
            'nonreportable_change_short' => 556,
            'nonreportable_long_pct' => 9.3,
            'nonreportable_short_pct' => 6.8,
            'source_payload' => [],
        ]);

        Http::fake([
            'https://publicreporting.cftc.gov/resource/6dca-aqww.json*' => Http::sequence()
                ->push([
                    ['report_date_as_yyyy_mm_dd' => '2026-06-09T00:00:00.000'],
                ], 200)
                ->push([
                    [
                        'id' => '260609099741F',
                        'market_and_exchange_names' => 'EURO FX - CHICAGO MERCANTILE EXCHANGE',
                        'contract_market_name' => 'EURO FX',
                        'cftc_contract_market_code' => '099741',
                        'report_date_as_yyyy_mm_dd' => '2026-06-09T00:00:00.000',
                        'open_interest_all' => '871507',
                        'noncomm_positions_long_all' => '219564',
                        'noncomm_positions_short_all' => '205632',
                        'comm_positions_long_all' => '511359',
                        'comm_positions_short_all' => '549444',
                        'nonrept_positions_long_all' => '90399',
                        'nonrept_positions_short_all' => '66246',
                        'change_in_noncomm_long_all' => '-15878',
                        'change_in_noncomm_short_all' => '19056',
                        'change_in_comm_long_all' => '31675',
                        'change_in_comm_short_all' => '364',
                        'change_in_nonrept_long_all' => '3860',
                        'change_in_nonrept_short_all' => '237',
                        'pct_of_oi_noncomm_long_all' => '25.2',
                        'pct_of_oi_noncomm_short_all' => '23.6',
                        'pct_of_oi_comm_long_all' => '58.7',
                        'pct_of_oi_comm_short_all' => '63.0',
                        'pct_of_oi_nonrept_long_all' => '10.4',
                        'pct_of_oi_nonrept_short_all' => '7.6',
                    ],
                ], 200)
                ->push([], 200),
        ]);

        $response = $this->getJson('/api/cot-sentiment?asset=EURUSD&refresh=1');

        $response->assertOk()
            ->assertJsonPath('data.synced_from_source', true)
            ->assertJsonPath('data.items.0.open_interest_all', 871507)
            ->assertJsonPath('data.items.0.categories.non_commercial.long_contracts', 219564)
            ->assertJsonPath('data.items.0.categories.non_commercial.short_contracts', 205632);

        $this->assertDatabaseHas('cot_reports', [
            'asset_symbol' => 'EURUSD',
            'report_date' => '2026-06-09',
            'open_interest_all' => 871507,
            'non_commercial_long' => 219564,
            'non_commercial_short' => 205632,
            'source_report_id' => '260609099741F',
        ]);
    }
}
