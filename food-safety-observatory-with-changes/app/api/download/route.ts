import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const file = searchParams.get("file");

  if (!file) {
    return new NextResponse("File parameter is required", { status: 400 });
  }

  // Prevent directory traversal attacks
  const safeFileName = path.basename(file);
  const allowedFiles = [
    "articles.csv",
    "articles.sample.csv",
    "current-data-report.json",
    "fssai-baselines.json",
    "taxonomy.json",
  ];

  if (!allowedFiles.includes(safeFileName)) {
    return new NextResponse("File not allowed or does not exist.", { status: 403 });
  }

  const filePath = path.join(process.cwd(), "data", safeFileName);

  try {
    const fileBuffer = await fs.readFile(filePath);
    
    // Determine the content type based on file extension
    const contentType = safeFileName.endsWith(".csv") ? "text/csv" : "application/json";
    
    return new NextResponse(fileBuffer, {
      headers: {
        "Content-Type": contentType,
        "Content-Disposition": `attachment; filename="${safeFileName}"`,
      },
    });
  } catch (error) {
    console.error("Error reading data file:", error);
    return new NextResponse("File not found on server", { status: 404 });
  }
}
