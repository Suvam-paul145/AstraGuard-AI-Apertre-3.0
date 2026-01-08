import { useState, useRef, useEffect, useCallback } from 'react';

/**
 * React Hook for Intelligent API Rate Limit
 * Simplified version for demo purposes
 */
export function useIntelligentApi(options: any = {}) {
  const [state, setState] = useState({
    loading: false,
    error: null as string | null,
    rateLimited: false,
    retryAfter: 0
  });
  
  const retryCountRef = useRef(0);

  const get = async (endpoint: string) => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    try {
      // Simulate API delay
      await new Promise(resolve => setTimeout(resolve, 500));
      return { success: true, data: {} };
    } catch (error) {
       const msg = error instanceof Error ? error.message : 'API error';
       setState(prev => ({ ...prev, error: msg }));
       return { success: false, error: msg };
    } finally {
       setState(prev => ({ ...prev, loading: false }));
    }
  };

  const post = async (endpoint: string, data: any) => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    try {
      // Simulate API delay
      await new Promise(resolve => setTimeout(resolve, 500));

      // Mock responses based on endpoint
      if (endpoint.includes('/federated-learning/status')) {
        return {
          success: true,
          data: {
            currentRound: 5,
            participants: ['node-1', 'node-2', 'node-3'],
            globalAccuracy: 0.92,
            localAccuracy: 0.88
          }
        };
      }

      return { success: true, data: { received: true } };
    } catch (error) {
       const msg = error instanceof Error ? error.message : 'API error';
       setState(prev => ({ ...prev, error: msg }));
       return { success: false, error: msg };
    } finally {
       setState(prev => ({ ...prev, loading: false }));
    }
  };

  return { get, post, ...state };
}

// Export compatibility hooks
export const useRateLimitNotifications = useIntelligentApi;
export const useSystemHealth = useIntelligentApi;
