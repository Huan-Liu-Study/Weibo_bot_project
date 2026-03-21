/**
 * API Service Layer for Weibo Bot Shield
 * Handles all network requests, wrapping them into neat asynchronous methods
 * separating concerns from DOM UI logic.
 */

const api = {
    detectTopic: async (topic, limit, isContinue, action = 'fetch', cookie = '') => {
        const res = await fetch('/api/detect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic, limit, continue: isContinue, action, cookie })
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        return data;
    },

    checkUser: async (uid) => {
        const res = await fetch('/api/check_user', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ uid })
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        return data;
    },

    getHistoryList: async () => {
        const res = await fetch('/api/history');
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        return data;
    },

    deleteTopic: async (topic) => {
        const res = await fetch('/api/delete_topic', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic })
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        return data;
    }
};

window.api = api;
