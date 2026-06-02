<?php

return [
    'warn_after_minutes' => (int) env('IDLE_SESSION_WARN_AFTER_MINUTES', 30),
    'grace_minutes' => (int) env('IDLE_SESSION_GRACE_MINUTES', 5),
    'expire_after_minutes' => (int) env('IDLE_SESSION_EXPIRE_AFTER_MINUTES', 35),
];
