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

    checkUser: async (uid, cookie = '') => {
        const res = await fetch('/api/check_user', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ uid, cookie })
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
    },

    getLabelQueue: async (topic = '', page = 1) => {
        const params = new URLSearchParams({ topic, page });
        const res = await fetch(`/api/label/queue?${params}`);
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        return data;
    },

    getLabeledQueue: async (topic = '', page = 1) => {
        const params = new URLSearchParams({ topic, page });
        const res = await fetch(`/api/label/labeled?${params}`);
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        return data;
    },

    deleteLabelUser: async (userId) => {
        const res = await fetch(`/api/label/delete/${userId}`, {
            method: 'DELETE'
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        return data;
    },

    submitLabel: async (userId, label, topic = '', aiPredScore = 0.5, features = {}, screenName = '') => {
        const res = await fetch('/api/label/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, label, topic, ai_pred_score: aiPredScore, features, screen_name: screenName })
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        return data;
    },

    getModelInfo: async () => {
        const res = await fetch('/api/model/info');
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        return data;
    },

    retrainModel: async () => {
        const res = await fetch('/api/model/retrain', { method: 'POST' });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        return data;
    },

    getMediaList: async () => {
        const res = await fetch('/api/media/list');
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        return data;
    },

    addMediaAccount: async (userId, screenName) => {
        const res = await fetch('/api/media/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, screen_name: screenName })
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        return data;
    },

    deleteMediaAccount: async (userId) => {
        const res = await fetch(`/api/media/delete/${userId}`, {
            method: 'DELETE'
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        return data;
    }
};

window.api = api;
