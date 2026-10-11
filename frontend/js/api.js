const API = '/api'; const api = { get: (p) => fetch(API + p).then(r => r.json()) };
