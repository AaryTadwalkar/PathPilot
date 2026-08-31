"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import {
  Eye,
  EyeOff,
  GraduationCap,
  Loader2,
} from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

import {
  signup,
  verifyOtp,
  login,
} from "@/services/auth.service";

import { saveAuth } from "@/lib/auth";

export default function AuthPage() {
  const router = useRouter();

  const [loading, setLoading] = useState(false);

  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  const [signUpEmail, setSignUpEmail] = useState("");
  const [signUpPassword, setSignUpPassword] = useState("");
  const [signUpConfirm, setSignUpConfirm] = useState("");

  const [otpMode, setOtpMode] = useState(false);
  const [otp, setOtp] = useState("");

  const [showLoginPassword, setShowLoginPassword] =
    useState(false);

  const [showSignupPassword, setShowSignupPassword] =
    useState(false);

  async function handleLogin(
    e: React.FormEvent
  ) {
    e.preventDefault();

    try {
      setLoading(true);

      const response = await login(
        loginEmail,
        loginPassword
      );

      const payload = JSON.parse(
        atob(
          response.access_token.split(".")[1]
        )
      );

      saveAuth(
        response.access_token,
        {
          id: payload.id,
          email: payload.sub,
          name: payload.name ?? ""
        }
      );

      router.push("/");

    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSignup(
    e: React.FormEvent
  ) {
    e.preventDefault();

    if (signUpPassword !== signUpConfirm) {
      alert("Passwords do not match");
      return;
    }

    try {
      setLoading(true);

      await signup(
        signUpEmail,
        signUpPassword
      );

      setOtpMode(true);

    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleOtp(
    e: React.FormEvent
  ) {
    e.preventDefault();

    try {

      setLoading(true);

      // 1. VERIFY OTP
      await verifyOtp(
        signUpEmail,
        otp
      );

      // 2. AUTO LOGIN
      const response = await login(
        signUpEmail,
        signUpPassword
      );

      // 3. DECODE JWT
      const payload = JSON.parse(
        atob(
          response.access_token.split(".")[1]
        )
      );

      // 4. SAVE AUTH
      saveAuth(
        response.access_token,
        {
          id: payload.id,
          email: payload.sub,
          name: payload.name ?? ""
        }
      );

      // 5. REDIRECT TO PROFILE SETUP
      router.push("/profile-setup");

    } catch (err: any) {

      alert(err.message);

    } finally {

      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-brand-bg flex items-center justify-center p-4">

      <div className="w-full max-w-md space-y-8">

        <div className="text-center">
          <div className="h-12 w-12 bg-brand-primary rounded-xl mx-auto flex items-center justify-center">
            <GraduationCap className="h-6 w-6 text-white" />
          </div>

          <h1 className="mt-4 text-2xl font-bold">
            PathPilot
          </h1>

          <p className="text-sm text-brand-text mt-1">
            AI-Powered Learning Assistant
          </p>
        </div>

        <Card className="border-brand-border shadow-xl">

          <CardHeader>
            <CardTitle>Welcome</CardTitle>
            <CardDescription>
              Continue to your dashboard
            </CardDescription>
          </CardHeader>

          <CardContent>

            <Tabs defaultValue="login">

              {!otpMode && (
                <TabsList className="grid grid-cols-2 mb-6">
                  <TabsTrigger value="login">
                    Log In
                  </TabsTrigger>

                  <TabsTrigger value="signup">
                    Sign Up
                  </TabsTrigger>
                </TabsList>
              )}

              <TabsContent value="login">

                <form
                  onSubmit={handleLogin}
                  className="space-y-4"
                >

                  <div>
                    <Label>Email</Label>

                    <Input
                      type="email"
                      value={loginEmail}
                      onChange={(e) =>
                        setLoginEmail(e.target.value)
                      }
                    />
                  </div>

                  <div>
                    <Label>Password</Label>

                    <div className="relative">

                      <Input
                        type={
                          showLoginPassword
                            ? "text"
                            : "password"
                        }
                        value={loginPassword}
                        onChange={(e) =>
                          setLoginPassword(e.target.value)
                        }
                      />

                      <button
                        type="button"
                        className="absolute right-3 top-1/2 -translate-y-1/2"
                        onClick={() =>
                          setShowLoginPassword((p) => !p)
                        }
                      >
                        {showLoginPassword ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                  </div>

                  <Button
                    type="submit"
                    className="w-full bg-brand-primary hover:bg-brand-primary"
                    disabled={loading}
                  >
                    {loading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      "Access Portal"
                    )}
                  </Button>
                </form>
              </TabsContent>

              <TabsContent value="signup">

                {!otpMode ? (
                  <form
                    onSubmit={handleSignup}
                    className="space-y-4"
                  >

                    <div>
                      <Label>Email</Label>

                      <Input
                        type="email"
                        value={signUpEmail}
                        onChange={(e) =>
                          setSignUpEmail(e.target.value)
                        }
                      />
                    </div>

                    <div>
                      <Label>Password</Label>

                      <div className="relative">

                        <Input
                          type={
                            showSignupPassword
                              ? "text"
                              : "password"
                          }
                          value={signUpPassword}
                          onChange={(e) =>
                            setSignUpPassword(e.target.value)
                          }
                        />

                        <button
                          type="button"
                          className="absolute right-3 top-1/2 -translate-y-1/2"
                          onClick={() =>
                            setShowSignupPassword((p) => !p)
                          }
                        >
                          {showSignupPassword ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </button>
                      </div>
                    </div>

                    <div>
                      <Label>Confirm Password</Label>

                      <Input
                        type="password"
                        value={signUpConfirm}
                        onChange={(e) =>
                          setSignUpConfirm(e.target.value)
                        }
                      />
                    </div>

                    <Button
                      type="submit"
                      className="w-full"
                    >
                      Create Account
                    </Button>
                  </form>

                ) : (

                  <form
                    onSubmit={handleOtp}
                    className="space-y-4"
                  >

                    <p className="text-sm text-brand-text">
                      OTP sent to {signUpEmail}
                    </p>

                    <Input
                      value={otp}
                      onChange={(e) =>
                        setOtp(e.target.value)
                      }
                      placeholder="Enter OTP"
                    />

                    <Button
                      type="submit"
                      className="w-full bg-brand-primary"
                    >
                      Confirm Identity
                    </Button>
                  </form>
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}