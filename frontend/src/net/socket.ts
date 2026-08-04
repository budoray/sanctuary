import { io, Socket } from 'socket.io-client';

const WS_PATH = '/ws/socket.io/';

export function connectSocket(): Socket {
  const socket = io({
    path: WS_PATH,
    transports: ['websocket', 'polling'],
  });

  socket.on('connect', () => {
    console.log('Socket connected:', socket.id);
  });

  socket.on('disconnect', () => {
    console.log('Socket disconnected');
  });

  return socket;
}
