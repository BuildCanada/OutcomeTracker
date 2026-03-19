import type { NextPageContext } from "next";

function ErrorPage({ statusCode }: { statusCode: number }) {
  return (
    <div style={{ padding: "2rem", textAlign: "center" }}>
      <h1>{statusCode}</h1>
      <p>
        {statusCode === 404
          ? "This page could not be found."
          : "An error occurred."}
      </p>
    </div>
  );
}

ErrorPage.getInitialProps = ({ res, err }: NextPageContext) => {
  const statusCode = res ? res.statusCode : err ? err.statusCode : 404;
  return { statusCode: statusCode ?? 500 };
};

export default ErrorPage;
