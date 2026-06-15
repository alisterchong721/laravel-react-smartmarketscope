<?php

namespace Tests\Unit;

use App\Http\Service\FundamentalScrapeService;
use Carbon\Carbon;
use PHPUnit\Framework\Attributes\DataProvider;
use ReflectionClass;
use Tests\TestCase;

class FundamentalScrapeServiceTest extends TestCase
{
    #[DataProvider('investingAndForexFactoryEventNameProvider')]
    public function test_investing_event_names_match_forex_factory_event_names(string $forexFactory, string $investing): void
    {
        $service = new FundamentalScrapeService();
        $reflection = new ReflectionClass($service);
        $method = $reflection->getMethod('canonicalCalendarEventKey');
        $method->setAccessible(true);

        $this->assertSame(
            $method->invoke($service, $forexFactory),
            $method->invoke($service, $investing)
        );
    }

    public function test_claimant_count_change_is_bearish_when_actual_beats_forecast_higher(): void
    {
        $service = new FundamentalScrapeService();
        $reflection = new ReflectionClass($service);
        $method = $reflection->getMethod('calculateCalendarImpact');
        $method->setAccessible(true);

        $this->assertSame(
            'Bearish',
            $method->invoke($service, 'UK Claimant Count Change', 26500.0, 23100.0, 26800.0)
        );
    }

    public function test_investing_event_page_actual_parser_handles_compact_history_rows(): void
    {
        $service = new FundamentalScrapeService();
        $reflection = new ReflectionClass($service);
        $method = $reflection->getMethod('parseInvestingEventPageActual');
        $method->setAccessible(true);

        $html = <<<'HTML'
            <html><body>
                Release date Time Actual Forecast Previous
                May 21, 2026 (Apr)01:30 4.5%4.3%

                4.3%
                Apr 16, 2026 (Mar)01:30 4.3%4.3%

                4.3%
                Show More
            </body></html>
        HTML;

        $event = $method->invoke(
            $service,
            $html,
            'Australia',
            'Australia Unemployment Rate',
            '2026-05-21'
        );

        $this->assertSame('4.5%', $event['actual_raw']);
        $this->assertSame(4.5, $event['actual']);
        $this->assertSame('4.3%', $event['forecast_raw']);
        $this->assertSame('4.3%', $event['previous_raw']);
    }

    public function test_investing_event_page_actual_parser_ignores_rows_before_release_time(): void
    {
        Carbon::setTestNow(Carbon::parse('2026-06-15 20:00:00', 'Asia/Kuala_Lumpur'));

        try {
            $service = new FundamentalScrapeService();
            $reflection = new ReflectionClass($service);
            $method = $reflection->getMethod('parseInvestingEventPageActual');
            $method->setAccessible(true);

            $html = <<<'HTML'
                <html><body>
                    Release date Time Actual Forecast Previous
                    Jun 15, 2026 (Jun)21:30 4.35%4.35%
                    May 05, 2026 (May)21:30 4.35%4.35%

                    4.10%
                    Show More
                </body></html>
            HTML;

            $this->assertNull($method->invoke(
                $service,
                $html,
                'Australia',
                'Australia Cash Rate',
                '2026-06-15',
                '21:30:00'
            ));
        } finally {
            Carbon::setTestNow();
        }
    }

    public function test_investing_event_page_actual_parser_handles_rows_without_period_label(): void
    {
        $service = new FundamentalScrapeService();
        $reflection = new ReflectionClass($service);
        $method = $reflection->getMethod('parseInvestingEventPageActual');
        $method->setAccessible(true);

        $html = <<<'HTML'
            <html><body>
                Release date Time Actual Forecast Previous
                Jul 15, 2026 13:45 2.25%
                Jun 10, 2026 13:45 2.25%2.25%

                2.25%
                Apr 29, 2026 13:45 2.25%2.25%

                2.25%
                Show More
            </body></html>
        HTML;

        $event = $method->invoke(
            $service,
            $html,
            'Canada',
            'Canada Overnight Rate',
            '2026-06-10'
        );

        $this->assertSame('2.25%', $event['actual_raw']);
        $this->assertSame(2.25, $event['actual']);
        $this->assertSame('2.25%', $event['forecast_raw']);
        $this->assertSame('2.25%', $event['previous_raw']);
    }

    public static function investingAndForexFactoryEventNameProvider(): array
    {
        return [
            'core cpi monthly' => ['US Core CPI m/m', 'Core CPI (MoM) (Apr)'],
            'cpi monthly' => ['US CPI m/m', 'CPI (MoM) (Apr)'],
            'cpi yearly' => ['US CPI y/y', 'CPI (YoY) (Apr)'],
            'ppi monthly' => ['US PPI m/m', 'PPI (MoM) (Apr)'],
            'uk gdp monthly' => ['UK GDP m/m', 'GDP (MoM) (Mar)'],
            'core retail sales monthly' => ['US Core Retail Sales m/m', 'Core Retail Sales (MoM) (Apr)'],
            'retail sales monthly' => ['US Retail Sales m/m', 'Retail Sales (MoM) (Apr)'],
            'core ppi monthly' => ['US Core PPI m/m', 'Core PPI (MoM) (Apr)'],
            'canada cpi monthly' => ['Canada CPI m/m', 'CPI (MoM) (Apr)'],
            'uk claimant count change' => ['UK Claimant Count Change', 'Claimant Count Change'],
            'uk cpi yearly' => ['UK CPI y/y', 'CPI (YoY) (Apr)'],
            'australia employment change' => ['Australia Employment Change', 'Employment Change (Apr)'],
            'australia unemployment rate' => ['Australia Unemployment Rate', 'Unemployment Rate (Apr)'],
            'uk manufacturing pmi' => ['UK Flash Manufacturing PMI', 'Manufacturing PMI (May)'],
            'uk services pmi' => ['UK Flash Services PMI', 'Services PMI (May)'],
            'australia cpi monthly' => ['Australia CPI m/m', 'CPI (MoM) (Q1)'],
            'australia cpi yearly' => ['Australia CPI y/y', 'CPI (YoY) (Q1)'],
            'australia trimmed mean cpi monthly' => ['Australia Trimmed Mean CPI m/m', 'Trimmed Mean CPI (MoM) (Q1)'],
            'us core pce monthly' => ['US Core PCE Price Index m/m', 'Core PCE Price Index (MoM) (Apr)'],
            'us prelim gdp quarterly' => ['US Prelim GDP q/q', 'GDP (QoQ) (Q1)'],
            'canada gdp monthly' => ['Canada GDP m/m', 'GDP (MoM) (Mar)'],
            'us adp employment change' => ['US ADP Non-Farm Employment Change', 'ADP Nonfarm Employment Change (May)'],
            'nzd official cash rate' => ['New Zealand Official Cash Rate', 'Interest Rate Decision'],
            'australia cash rate' => ['Australia Cash Rate', 'Interest Rate Decision'],
            'canada overnight rate' => ['Canada Overnight Rate', 'Interest Rate Decision'],
        ];
    }
}
