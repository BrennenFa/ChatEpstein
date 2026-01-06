import { NextRequest, NextResponse } from 'next/server';

// Generate unique session ID for each user
function generateSessionId(): string {
  return `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

export async function POST(request: NextRequest) {
  try {
    const { question, sessionId } = await request.json();

    if (!question) {
      return NextResponse.json(
        { error: 'Question is required' },
        { status: 400 }
      );
    }

    // Use provided session ID or generate new one
    const userSessionId = sessionId || generateSessionId();

    // Call FastAPI backend
    const BACKEND_URL = process.env.BACKEND_URL;
    const API_KEY = process.env.BACKEND_API_KEY;

    if (!API_KEY) {
      throw new Error('BACKEND_API_KEY environment variable is not set');
    }

    const response = await fetch(`${BACKEND_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
      },
      body: JSON.stringify({
        message: question,
        session_id: userSessionId
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Backend request failed');
    }

    const data = await response.json();


    // Transform FastAPI response to frontend format
    const formattedResponse = {
      answer: data.answer,
      citations: data.citations || {},
      sessionId: data.session_id,
      tokensUsed: data.tokens_used,
      promptTokens: data.prompt_tokens,
      completionTokens: data.completion_tokens,
    };


    return NextResponse.json(formattedResponse);
  } catch (error) {
    console.error('Error processing chat request:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    );
  }
}
