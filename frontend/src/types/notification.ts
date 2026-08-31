export interface NotificationItem {
  type: string;
  title: string;
  message: string;
  created_at: string;
}

export interface NotificationResponse {
  unread_count: number;
  notifications: NotificationItem[];
}