import { UserForm } from '@/components/auth/user-form';

export default async function EditUserPage({ params }: { params: { id: string } }) {
  const userId = Number(params.id);
  if (!Number.isInteger(userId) || userId < 1) {
    return <main className="p-8">Invalid user identifier.</main>;
  }
  return <UserForm userId={userId} />;
}
