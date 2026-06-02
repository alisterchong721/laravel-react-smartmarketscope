<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Symfony\Component\DomCrawler\Crawler;

class SiteCheckController extends Controller
{
    public function check($url)
    {
        try {
            // Get page content
            $response = Http::withHeaders([
                'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
            ])->get($url);

            if (!$response->successful()) {
                return "⚠️ Site returned status: " . $response->status();
            }

            $html = $response->body();

            // Check if page contains JavaScript-loaded content
            if (strpos($html, 'id="root"') || strpos($html, '<script') !== false) {
                $dynamicDetected = true;
            } else {
                $dynamicDetected = false;
            }

            // Parse static content using DomCrawler
            $crawler = new Crawler($html);
            $title = $crawler->filter('title')->count() ? $crawler->filter('title')->text() : 'No title found';

            return [
                'accessible' => true,
                'url' => $url,
                'page_title' => $title,
                'dynamic_content_detected' => $dynamicDetected
            ];

        } catch (\Exception $e) {
            return [
                'accessible' => false,
                'error' => $e->getMessage()
            ];
        }
    }
}
