<?php

namespace App\Http\Controllers;

use App\Models\User;
use App\Models\PasswordReset;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Mail;
use App\Mail\PasswordResetMail;

class PasswordResetController extends Controller
{
    public function forgotPassword(Request $request)
    {
        $validated = $request->validate(['email' => 'required|email']);
        
        $user = User::findByEmail($validated['email']);
        
        if (!$user) {
            return response()->json([
                'success' => false,
                'message' => 'Email is not registered'
            ], 404);
        }

        $code = (string) random_int(100000, 999999);
        PasswordReset::createCode($user->email, $code);

        try {
            Mail::to($user->email)->send(new PasswordResetMail($code, $user->email));
            
            return response()->json([
                'success' => true,
                'message' => 'Password reset code sent to your email',
                'data' => [
                    'email' => $user->email,
                    'expires_in_minutes' => 10
                ]
            ], 202);
            
        } catch (\Exception $e) {
            PasswordReset::deleteByEmail($user->email);

            return response()->json([
                'success' => false,
                'message' => 'Failed to send reset email'
            ], 500);
        }
    }

    public function validateToken(Request $request)
    {
        $validated = $request->validate([
            'email' => 'required|email',
            'code' => 'required|digits:6'
        ]);

        $isValid = PasswordReset::validateCode($validated['email'], $validated['code']);

        if (!$isValid) {
            return response()->json([
                'success' => false,
                'message' => 'Invalid or expired verification code'
            ], 400);
        }

        return response()->json([
            'success' => true,
            'message' => 'Verification code is valid'
        ]);
    }

    public function resetPassword(Request $request)
    {
        $validated = $request->validate([
            'email' => 'required|email',
            'code' => 'required|digits:6',
            'password' => 'required|confirmed|min:6'
        ]);

        $success = PasswordReset::resetPassword(
            $validated['email'],
            $validated['code'],
            $validated['password']
        );

        if (!$success) {
            return response()->json([
                'success' => false,
                'message' => 'Invalid or expired verification code'
            ], 400);
        }

        return response()->json([
            'success' => true,
            'message' => 'Password reset successfully'
        ]);
    }
}
