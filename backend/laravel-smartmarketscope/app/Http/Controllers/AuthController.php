<?php

namespace App\Http\Controllers;

use App\Mail\RegistrationVerificationMail;
use App\Models\PendingUserRegistration;
use App\Models\User;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Mail;

class AuthController extends Controller
{
    public function register(Request $request)
    {
        $validated = $request->validate([
            'email' => 'required|email|unique:users',
            'password' => 'required|confirmed|min:6'
        ]);

        $code = (string) random_int(100000, 999999);

        PendingUserRegistration::createFor(
            $validated['email'],
            $validated['password'],
            $code
        );

        try {
            Mail::to($validated['email'])->send(new RegistrationVerificationMail($code));
        } catch (\Exception $e) {
            PendingUserRegistration::where('email', $validated['email'])->delete();

            return response()->json([
                'message' => 'Failed to send verification email'
            ], 500);
        }

        return response()->json([
            'message' => 'Verification code sent to your email',
            'data' => [
                'email' => $validated['email'],
                'expires_in_minutes' => 10
            ]
        ], 202);
    }

    public function verifyRegistration(Request $request)
    {
        $validated = $request->validate([
            'email' => 'required|email',
            'code' => 'required|digits:6'
        ]);

        $result = DB::transaction(function () use ($validated) {
            $pendingRegistration = PendingUserRegistration::where('email', $validated['email'])
                ->lockForUpdate()
                ->first();

            if (!$pendingRegistration || $pendingRegistration->isExpired()) {
                optional($pendingRegistration)->delete();

                return [
                    'error' => true,
                    'status' => 400,
                    'message' => 'Invalid or expired verification code'
                ];
            }

            if (!$pendingRegistration->codeMatches($validated['code'])) {
                return [
                    'error' => true,
                    'status' => 400,
                    'message' => 'Invalid or expired verification code'
                ];
            }

            if (User::existsByEmail($pendingRegistration->email)) {
                $pendingRegistration->delete();

                return [
                    'error' => true,
                    'status' => 409,
                    'message' => 'Email is already registered'
                ];
            }

            $user = User::createUser(
                $pendingRegistration->email,
                $pendingRegistration->password,
                now()
            );

            $pendingRegistration->delete();

            $token = $user->createToken(
                'auth_token',
                ['*'],
                now()->addMinutes(config('idle_session.expire_after_minutes'))
            )->plainTextToken;

            return [
                'error' => false,
                'user' => [
                    'id' => $user->id,
                    'email' => $user->email,
                ],
                'token' => $token,
                'token_type' => 'Bearer'
            ];
        });

        if ($result['error']) {
            return response()->json([
                'message' => $result['message']
            ], $result['status']);
        }

        return response()->json([
            'message' => 'User registered successfully',
            'data' => [
                'user' => $result['user'],
                'token' => $result['token'],
                'token_type' => $result['token_type']
            ]
        ], 201);
    }

    public function resendRegistrationCode(Request $request)
    {
        $validated = $request->validate([
            'email' => 'required|email'
        ]);

        $pendingRegistration = PendingUserRegistration::where('email', $validated['email'])->first();

        if (!$pendingRegistration || $pendingRegistration->isExpired()) {
            optional($pendingRegistration)->delete();

            return response()->json([
                'message' => 'No pending registration found for this email'
            ], 404);
        }

        if (!$pendingRegistration->canResendCode()) {
            return response()->json([
                'message' => 'Verification code was already sent. Please wait before requesting another code.',
                'data' => [
                    'retry_after_seconds' => $pendingRegistration->secondsUntilResend()
                ]
            ], 429);
        }

        $code = (string) random_int(100000, 999999);
        $pendingRegistration->refreshCode($code);

        try {
            Mail::to($pendingRegistration->email)->send(new RegistrationVerificationMail($code));
        } catch (\Exception $e) {
            return response()->json([
                'message' => 'Failed to send verification email'
            ], 500);
        }

        return response()->json([
            'message' => 'Verification code sent to your email',
            'data' => [
                'email' => $pendingRegistration->email,
                'expires_in_minutes' => 10,
                'retry_after_seconds' => 300
            ]
        ], 202);
    }

    public function login(Request $request)
    {
        $validated = $request->validate([
            'email' => 'required|email',
            'password' => 'required'
        ]);

        $user = User::findByEmail($validated['email']);

        if (!$user || !Hash::check($validated['password'], $user->password)) {
            return response()->json([
                'message' => 'Invalid email or password'
            ], 401);
        }

        $token = $user->createToken(
            'auth_token',
            ['*'],
            now()->addMinutes(config('idle_session.expire_after_minutes'))
        )->plainTextToken;

        return response()->json([
            'message' => 'Login successful',
            'data' => [
                'user' => [
                    'id' => $user->id,
                    'email' => $user->email
                ],
                'token' => $token,
                'token_type' => 'Bearer'
            ]
        ]);
    }

    public function logout(Request $request)
    {
        $request->user()->currentAccessToken()->delete();
        return response()->json(['message' => 'Logged out successfully']);
    }

    public function logoutAll(Request $request)
    {
        $request->user()->revokeAllTokens();
        return response()->json(['message' => 'Logged out from all devices']);
    }

    public function me(Request $request)
    {
        return response()->json([
            'data' => $request->user()
        ]);
    }

    public function keepAlive(Request $request)
    {
        return response()->json([
            'message' => 'Session extended',
            'data' => [
                'warn_after_minutes' => config('idle_session.warn_after_minutes'),
                'grace_minutes' => config('idle_session.grace_minutes'),
                'expires_at' => $request->user()?->currentAccessToken()?->expires_at,
            ],
        ]);
    }

    public function updateProfile(Request $request)
    {
        $user = $request->user();
        
        $validated = $request->validate([
            'email' => 'sometimes|email|unique:users,email,' . $user->id,
            'password' => 'sometimes|confirmed|min:6'
        ]);

        if (isset($validated['email'])) {
            $user->email = $validated['email'];
        }

        if (isset($validated['password'])) {
            $user->updatePassword($validated['password']);
        }

        $user->save();

        return response()->json([
            'message' => 'Profile updated successfully',
            'data' => [
                'id' => $user->id,
                'email' => $user->email
            ]
        ]);
    }
}
