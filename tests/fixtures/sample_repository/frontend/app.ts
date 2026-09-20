import React from 'react';

export interface UserProps {
    name: string;
    email: string;
}

export class UserComponent {
    constructor(props: UserProps) {
        this.props = props;
    }

    render() {
        return null;
    }
}

export function calculate(a: number, b: number): number {
    return a + b;
}

export const helper = () => {};
