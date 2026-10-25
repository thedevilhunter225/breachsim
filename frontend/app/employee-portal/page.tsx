import type { Metadata } from "next";

import { EmployeePortal } from "@/components/employee-portal";

export const metadata: Metadata = {
  title: "Employee portal",
  robots: { index: false, follow: false },
};

export default function EmployeePortalPage() {
  return <EmployeePortal />;
}
