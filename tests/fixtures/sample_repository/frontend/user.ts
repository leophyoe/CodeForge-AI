import { User } from './app';

export function getUser(id: string): User | null {
    return null;
}

export type Status = 'active' | 'inactive';

export enum Roles {
    Admin = 'ADMIN',
    User = 'USER',
}
